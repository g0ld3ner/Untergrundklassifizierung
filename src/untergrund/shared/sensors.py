from typing import Callable, Iterable, Protocol, cast
from inspect import signature
from functools import wraps 
import re

####### decorator mit selectionsfunktion
type SensorDict[T] = dict[str, T]
type SensorName = str | None

class SensorStep[T](Protocol):
    """Callable mit Broadcast-Unterstützung plus .select(...)-Fabrik."""
    def __call__(self, x: T | SensorDict[T]) -> T | SensorDict[T]: ...
    def select(
        self,
        *,
        include: Iterable[str] | None = None,
        exclude: Iterable[str] | None = None,
        regex: str | None = None,
        predicate: Callable[[str, T], bool] | None = None,
    ) -> "SensorStep[T]": ...


def apply_to_all_sensors[T](func: Callable[..., T]) -> SensorStep[T]:
    """
    Decorator: Macht aus einer Input->Output Funktion eine,
    die auch dict[str, Input] -> dict[str, Output] versteht.
    Falls die Funktion ein Argument `sensor_name` akzeptiert,
    wird der Dict-Key automatisch als 'sensor_name' übergeben.
    Zusätzlich gibt es die Mathode .select(...), um die Funktion nur auf
    bestimmte Keys im Dict anzuwenden.
    - "sensor_name" wird als **kw-only** Argument erwartet (Signatur: (x, *, sensor_name=...)).
    - ".select(...)" wirkt nicht bei Einzelobjekten (DF).
    """

    accepts_name = "sensor_name" in signature(func).parameters

    def apply(name: SensorName, value: T) -> T:
        """Wendet func(value) an; setzt sensor_name nur wenn akzeptiert."""
        if accepts_name:
            return func(value, sensor_name=name)  # type: ignore[misc]
        else:
            return func(value)

    @wraps(func)
    def wrapper(x: T | dict[str, T]) -> T | dict[str, T]:
        if isinstance(x, dict):
            out: dict[str, T] = {}
            for name, value in x.items():
                out[name] = apply(name, value)
            return out
        else:
            return apply(None, x)

    def select(
        *,
        include: Iterable[str] | None = None,
        exclude: Iterable[str] | None = None,
        regex: str | None = None,
        predicate: Callable[[str, T], bool] | None = None,
    ) -> SensorStep[T]:
        inc = set(include) if include else None
        exc = set(exclude) if exclude else None
        rx  = re.compile(regex) if regex else None

        def is_selected(name: str, value: T) -> bool:
            if inc is not None and name not in inc: return False
            if exc is not None and name in exc:     return False
            if rx is not None and rx.search(name) is None: return False
            if predicate is not None and not predicate(name, value): return False
            return True

        @wraps(func)
        def selective_wrapper(x: T | dict[str, T]) -> T | dict[str, T]:
            if isinstance(x, dict):
                out: dict[str, T] = {}
                for name, value in x.items():
                    if is_selected(name, value):
                        out[name] = apply(name, value)
                    else:
                        out[name] = value
                return out
            else:
                return apply(None, x)

        selective_wrapper.select = select  # type: ignore[attr-defined]
        return cast(SensorStep[T], selective_wrapper)

    wrapper.select = select  # type: ignore[attr-defined]
    return cast(SensorStep[T], wrapper)