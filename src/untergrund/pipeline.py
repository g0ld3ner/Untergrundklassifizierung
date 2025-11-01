from dataclasses import is_dataclass, replace, fields as dc_fields
from typing import Callable, Optional, Any, Sequence
from inspect import signature, Parameter
from functools import partial
import copy


# ---------- kleine Utilities (lokal, ohne Decorator-Kopplung) ----------

def _defensive_copy_kwargs(kw: dict[str, Any]) -> dict[str, Any]:
    """Shallow-Kopie mutabler kwarg-Werte (best-effort)."""
    safe: dict[str, Any] = {}
    for k, v in kw.items():
        if hasattr(v, "copy") and callable(getattr(v, "copy")):
            try:
                safe[k] = v.copy()
                continue
            except Exception:
                pass
        safe[k] = v
    return safe


def _validate_kwargs_for_fn(fn: Callable[..., Any], fn_kwargs: dict[str, Any]) -> None:
    """
    Erlaubt nur keyword-fähige Parameter (oder **kwargs), aber NIE 'sensor_name'.
    Wird genutzt, wenn kein 'with_kwargs' vorhanden ist.
    """
    if "sensor_name" in fn_kwargs:
        raise TypeError("Passing 'sensor_name' via fn_kwargs is not allowed (reserved for decorators).")

    sig = signature(fn)
    params = sig.parameters.values()

    # **kwargs → alles erlaubt (abgesehen von sensor_name)
    if any(p.kind == Parameter.VAR_KEYWORD for p in params):
        return

    allowed = {p.name for p in params if p.kind in (Parameter.POSITIONAL_OR_KEYWORD, Parameter.KEYWORD_ONLY)}
    unknown = set(fn_kwargs) - allowed
    if unknown:
        raise TypeError(
            f"Unknown kwargs for {getattr(fn,'__name__',repr(fn))}: {sorted(unknown)} | allowed: {sorted(allowed)}"
        )


def _label_for_callable(f: Callable[..., Any]) -> str:
    """
    Saubere Label-Darstellung:
    - functools.partial → name(k=v, ...)
    - sonst __name__ oder Klassenname
    - Werte werden gekürzt, Keys alphabetisch.
    """
    def _short(v: Any, maxlen: int = 1000) -> str:
        s = repr(v)
        return s if len(s) <= maxlen else (s[:maxlen] + "…")
    try:
        # 1) Bevorzugt Metadaten vom Decorator
        if hasattr(f, "_base_name"):
            base = getattr(f, "_base_name")
            kw = getattr(f, "_bound_kwargs", None) or {}
            if kw:
                if "cfg" in kw.keys():  # Sonderbehandlung für große Config-Dicts
                    kw = kw.copy()
                    kw["cfg"] = "{...}"
                items = [f"{k}={_short(kw[k])}" for k in sorted(kw)]
                return f"{base}({', '.join(items)})"
            return base
        # 2) functools.partial
        if isinstance(f, partial):
            base = getattr(f.func, "__name__", f.func.__class__.__name__)
            kw = getattr(f, "keywords", None) or {}
            if kw:
                if "cfg" in kw.keys():  # Sonderbehandlung für große Config-Dicts
                    kw = kw.copy()
                    kw["cfg"] = "{...}"
                items = [f"{k}={_short(kw[k])}" for k in sorted(kw)]
                return f"{base}({', '.join(items)})"
            return base
        # 3) Fallback: __name__ oder Klassenname
        return getattr(f, "__name__", f.__class__.__name__)
    except Exception:
        return repr(f)
    # OLD:
    # try:
    #     # functools.partial?
    #     if isinstance(f, partial):
    #         base = getattr(f.func, "__name__", f.func.__class__.__name__)
    #         kw = getattr(f, "keywords", None) or {}
    #         if kw:
    #             items = []
    #             for k in sorted(kw):
    #                 v = repr(kw[k])
    #                 v = (v[:30] + "…") if len(v) > 5000 else v
    #                 items.append(f"{k}={v}")
    #             return f"{base}({', '.join(items)})"
    #         return base
    #     # Wrapper mit __name__
    #     name = getattr(f, "__name__", None)
    #     return name or f.__class__.__name__
    # except Exception:
    #     return repr(f)


# ---------- CtxPipeline: Ctx→Ctx Pipeline für dataclasses ----------

class CtxPipeline:
    """
    Ctx→Ctx-Pipeline für reine Datenfunktionen (ohne Ctx-Wissen).

    Leitplanken:
    - Nur Routing über .add(fn, ...):
        * Single-Source → Single-Dest (Standard)
        * Single-Source → In-Place (dest fehlt ⇒ dest = source)
        * Multi-Source → Single-Dest (Combine)
      KEIN Fan-Out, KEIN direkter Ctx-Step.
    - Updates erfolgen immutable via dataclasses.replace(ctx, ...).
    - Tap/Inspect ist read-only (Ctx bleibt unverändert).

    API:
      add(fn, *, source: str | Sequence[str], dest: Optional[str] = None, 
          name: Optional[str] = None, fn_kwargs: Optional[dict[str, Any]] = None)
        - source=str:    fn bekommt genau dieses Teilobjekt.
                         dest=None ⇒ In-Place (dest=source).
        - source=list:   fn(*values) in Reihenfolge von `source`.
                         dest MUSS gesetzt sein.
        - name:          Optionaler Anzeigename (repr / Fehlermeldungen).
        - fn_kwargs:     Nur Keyword-Parameter; werden früh validiert/gebunden.

      tap(inspector, *, projector=None, deepcopy=True, name=None)
        - Inspector erhält IMMER ein dict[str, Any]:
            * source=str, value ist dict → direkt durchreichen (flach).
            * source=str, value ist single → {source: value}.
            * source=list → für jede Quelle:
                - dict-Quellen werden in das Ergebnis gemerged,
                - Single-Quellen unter ihrem Quellnamen hinzugefügt.
        - deepcopy=True: es wird eine tiefe Kopie des gesamten dicts erstellt.
        - Rückgaben des Inspectors werden ignoriert; bei Rückgabe != None erfolgt eine Warnung.
    """

    def __init__(self):
        self.steps: list[Callable[[Any], Any]] = []
        self.taps: dict[str, list] = {}

    # ---------- Core execution ----------

    def __call__(self, ctx: Any) -> Any:
        if not is_dataclass(ctx):
            raise TypeError("CtxPipeline erwartet ein dataclass-Objekt als ctx.")
        for i, f in enumerate(self.steps, start=1):
            step_name = getattr(f, "__name__", repr(f))
            try:
                ctx = f(ctx)
            except Exception as e:
                raise RuntimeError(f"Pipeline-Fehler in Step {i:02} {step_name}: {e}") from e
            if ctx is None:
                raise RuntimeError(f"Step {i:02} {step_name} hat nichts zurückgegeben!")
        return ctx

    def __repr__(self) -> str:
        if not self.steps:
            return "CtxPipeline: (empty)"
        names = [getattr(f, "__name__", repr(f)) for f in self.steps]
        numbered = [f"{i:02}  {nm}" for i, nm in enumerate(names, start=1)]
        return "CtxPipeline:\n  " + "\n  ".join(numbered)

    # ---------- Public API ----------

    def add(
        self,
        fn: Callable[..., Any],
        *,
        source: str | Sequence[str],
        dest: Optional[str] = None,
        name: Optional[str] = None,
        fn_kwargs: Optional[dict[str, Any]] = None,
    ) -> "CtxPipeline":
        """
        Hängt einen Routing-Step an. Funktion steht immer vorn.
        - Single-Source:  source=str, dest optional (In-Place wenn None)
        - Multi-Source:   source=list[str], dest Pflicht
        - fn_kwargs:      Nur Keyword-Parameter; früh validiert/gebunden.
                          Falls `fn.with_kwargs` existiert → wird bevorzugt genutzt.
                          Sonst Fallback via functools.partial(fn, **kw).
        """
        # --- Parametrisierung (ohne Kopplung) ---
        bound_fn = fn
        if fn_kwargs:
            # bevorzugt dekoratorseitige API (falls vorhanden)
            if hasattr(fn, "with_kwargs") and callable(getattr(fn, "with_kwargs")):
                try:
                    bound_fn = fn.with_kwargs(**fn_kwargs)  # type: ignore[attr-defined]
                except TypeError as e:
                    raise TypeError(f"with_kwargs() rejected keys for {getattr(fn,'__name__',repr(fn))}: {e}") from e
            else:
                _validate_kwargs_for_fn(fn, fn_kwargs)
                bound_fn = partial(fn, **_defensive_copy_kwargs(fn_kwargs))

        # Label (falls kein custom name)
        auto_label = _label_for_callable(bound_fn)
        compiled = self._compile_route(bound_fn, source=source, dest=dest, name=(name or auto_label))
        self.steps.append(compiled)
        return self

    def tap(
        self,
        inspector: Callable[[Any], None],
        *,
        source: str | Sequence[str],
        name: Optional[str] = None,
        deepcopy: bool = True,
    ) -> "CtxPipeline":
        """
        Inspektions-Step (read-only):
        - source: Pflicht. Einzelner string oder mehrere Sequence[str].
        - inspector: Funktion, welche die extrahierten Daten inspiziert.
            * Dem Inspektor wird IMMER ein dict[str, Any] übergeben.
            * Rückgabewerte des Inspektors werden ignoriert; bei Rückgabe != None erfolgt eine Warnung.
        - deepcopy: True (Standard) => schützt sicher vor versehentlichen Mutationen.
        - name: optionaler Anzeigename (nur für __repr__/Debug).

        Gibt den unveränderten Ctx weiter.
        """
        step_name = name or getattr(inspector, "__name__", "tap")

        # Deepcopy Warnung
        if not deepcopy:
            print(f"WARNUNG: tap({step_name}, deepcopy=False) – Mutationen am Ctx sind möglich!")

        def _project(ctx: Any) -> Any:
            # Einheitlicher Vertrag für Inspektoren: immer dict[str, Any]
            if isinstance(source, str):
                value = getattr(ctx, source)
                if isinstance(value, dict):
                    items = value
                else:
                    items = {source: value}
            else:
                # mehrere Quellen → benanntes dict in Quellreihenfolge
                items: dict[str, Any] = {}
                for s in source:
                    v = getattr(ctx, s)
                    if isinstance(v, dict):
                        # Merge: Key wird überschrieben falls schon verhanden! -> Warnung
                        overlap = items.keys() & v.keys()
                        if overlap:
                            print(f"[Warnung] Doppelte Keys beim Merge aus Quelle '{s}': {sorted(overlap)}")
                        items.update(v)
                    else:
                        items[s] = v
            return copy.deepcopy(items) if deepcopy else items


            #     items = {source: getattr(ctx, source)}
            # else:
            #     # mehrere Quellen → benanntes dict in Quellreihenfolge
            #     items = {s: getattr(ctx, s) for s in source}
            # return copy.deepcopy(items) if deepcopy else items
            ##OLD
            #     data = getattr(ctx, source)
            #     return copy.deepcopy(data) if deepcopy else data
            # # mehrere Quellen -> gleiches Tupel, in Reihenfolge der Namen
            # items = tuple(getattr(ctx, s) for s in source)
            # return copy.deepcopy(items) if deepcopy else items

        def _tap(ctx: Any) -> Any:
            view = _project(ctx)
            result = inspector(view)   # Inspektor bekommt IMMER dict[str, Any]
            if result is not None:
                print(f"[Warnung] Tap-Inspektor {step_name} hat etwas zurückgegeben! Return wird aber ignoriert ;)")
            return ctx        # Ctx bleibt unverändert

        _tap.__name__ = f"tap({step_name})"
        self.steps.append(_tap)
        return self

    # ---------- Internals ----------

    @staticmethod
    def _dataclass_fields_set(ctx_type: type) -> set[str]:
        try:
            return {f.name for f in dc_fields(ctx_type)}
        except Exception:
            return set()

    def _compile_route(
        self,
        fn: Callable[..., Any],
        *,
        source: str | Sequence[str],
        dest: Optional[str],
        name: Optional[str],
    ) -> Callable[[Any], Any]:
        # Normalisiere Quellen
        if isinstance(source, str):
            sources: list[str] = [source]
        else:
            sources = list(source)
            if not sources:
                raise ValueError("add(...): source-Liste ist leer.")
        multi_source = len(sources) > 1

        # Dest-Policy
        if multi_source and not dest:
            raise ValueError("add(...): Bei Multi-Source MUSS dest gesetzt sein.")
        # Single-Source In-Place
        if not multi_source and dest is None:
            dest = sources[0]

        # Step-Name
        left = "+".join(sources) if multi_source else sources[0]
        label = name or _label_for_callable(fn)
        step_name = f"{left} → {dest}: {label}"

        def _apply(ctx: Any) -> Any:
            # Validierung der Felder am realen ctx-Objekt
            if not is_dataclass(ctx):
                raise TypeError(f"{step_name}: ctx ist keine dataclass – replace() nicht möglich.")
            ctx_fields = self._dataclass_fields_set(type(ctx))
            for s in sources:
                if s not in ctx_fields:
                    raise AttributeError(f"{step_name}: Ctx hat kein Feld '{s}'.")
            if dest not in ctx_fields:
                raise AttributeError(f"{step_name}: Ctx hat kein Ziel-Feld '{dest}'.")

            # Eingaben aus ctx holen
            inputs = [getattr(ctx, s) for s in sources]
            # Aufruf der reinen Funktion
            try:
                new_value = fn(*inputs) if multi_source else fn(inputs[0])
            except TypeError as e:
                raise TypeError(f"{step_name}: Signatur passt nicht zu Quellen {sources}: {e}") from e

            # Immutable Update
            return replace(ctx, **{dest: new_value})  # pyright: ignore[reportArgumentType]

        _apply.__name__ = step_name
        return _apply


def bridge(*fns: Callable[[Any], Any], name: Optional[str] = None) -> Callable[[Any], Any]:
    """
    Kapselt mehrere reine Funktionen zu einem unary-Step f(x)->y.

    Zweck: Ephemere Zwischenschritte (Tin->...->Tout) innerhalb von CtxPipeline
    abbilden, ohne temporäre Felder im Ctx zu benötigen. Eignet sich z. B. für
    config -> path -> DataFrame -> sensors.

    Verhalten: Wendet die Funktionen der Reihe nach auf den Wert an. Wenn ein
    Step None zurückgibt, wird ein RuntimeError geworfen (analog zu Pipeline).
    """
    if not fns:
        raise ValueError("bridge(...): mindestens eine Funktion erforderlich.")

    fn_names = [getattr(f, "__name__", repr(f)) for f in fns]
    label = name or "bridge(" + "|".join(fn_names) + ")"

    def _apply(x: Any) -> Any:
        y = x
        for f in fns:
            y = f(y)
            if y is None:
                raise RuntimeError(
                    f"{label}: Step {getattr(f, '__name__', repr(f))} hat nichts zurückgegeben!"
                )
        return y

    _apply.__name__ = label
    return _apply
