# Architecture Decision Records (ADRs)

**Last Updated:** 2025-12-21
**Status:** ✅ Active (Append-Only)

Dieses Dokument sammelt alle architektonischen Entscheidungen chronologisch. ADRs werden nie gelöscht, nur als "Superseded" markiert.

---

# ADR 001 – Keine Stage-Toggles

## Status
Accepted

## Kontext
Die Pipeline ist in feste Stages unterteilt (`INGEST → SELECT → PREPROCESS → WINDOW → FEATURES → MODEL → EXPORT`).  
In vielen Frameworks ist es üblich, einzelne Stages per Konfiguration ein- oder auszuschalten.  
Das könnte auf den ersten Blick nützlich wirken für Experimente oder Debugging.

## Entscheidung
**Alle Stages laufen immer in fester Reihenfolge.**  
- Jede Stage ist ein *Runner*, der garantiert ein `Ctx` entgegennimmt und zurückgibt.  
- Wenn eine Stage keine Arbeit zu erledigen hat, reicht sie den `Ctx` unverändert weiter (No-Op).  
- „Stage-Toggles“ über die Config oder CLI sind **nicht vorgesehen**.

## Begründung
- **Einfachheit:** Das Orchestrator-Gerüst bleibt minimal und deterministisch.  
- **Vorhersagbarkeit:** Jede Ausführung durchläuft denselben Ablauf, kein Sonderfall durch deaktivierte Stages.  
- **Robustheit:** Ein Runner, der nichts zu tun hat, verursacht keinen Bruch, sondern gibt `Ctx` unverändert zurück.  
- **Erweiterbarkeit:** Neue Stages lassen sich einfügen, ohne dass die Logik für „Stage-Toggles“ gepflegt werden muss.

## Konsequenzen
- **Pro:** Keine zusätzliche Komplexität in Config und Orchestrator.  
- **Pro:** Höhere Konsistenz und Testbarkeit.  
- **Contra:** Für Debugging/Experimente muss eine Stage ggf. temporär „leer“ implementiert oder lokal kommentiert werden.  
- **Mitigation:** Für Debugging gibt es `tap`-Funktionen, um Zwischenergebnisse einzusehen, sowie Tests für gezielte Stages.

---

# ADR 002 – Einheitliche Zeitzone: UTC

## Status
Accepted

## Kontext
Sensor-Daten enthalten Zeitstempel (z. B. Nanosekunden seit Epoche).  
In Projekten mit mehreren Datenquellen entstehen oft Probleme durch Zeitzonen, Sommer-/Winterzeit (DST) oder lokale Formate.  
Uneinheitliche Zeitzonen erschweren Preprocessing, Windowing, Export und spätere Modellbewertung.

## Entscheidung
**Alle Zeitangaben werden intern strikt in UTC verarbeitet.**  
- Rohdaten werden beim Einlesen auf UTC normalisiert.  
- Zeitindex-Felder in DataFrames heißen konsequent `time_utc`.  
- Alle internen Operationen (Sortieren, Resampling, Windowing) erfolgen in UTC.  
- Lokale Zeitzonen (z. B. „Europe/Berlin“) sind nur beim Export oder für Nutzer-Darstellung erlaubt.

## Begründung
- **Eindeutigkeit:** UTC ist eine weltweite Referenz, vermeidet DST-Probleme.  
- **Reproduzierbarkeit:** Modelle und Tests liefern konsistente Ergebnisse, unabhängig von der lokalen Umgebung.  
- **Einfachheit:** Keine komplexe Logik in Preprocessing oder Export für Zeitzonen-Umrechnung.

## Konsequenzen
- **Pro:** Klare Linie, konsistenter Zeitbezug im gesamten Projekt.  
- **Pro:** Weniger Bugs durch Sommer-/Winterzeit oder lokale Abweichungen.  
- **Contra:** Nutzer erwarten oft lokale Zeiten → Umrechnung beim Export/Frontend nötig.  
- **Mitigation:** Export-Stages dürfen zusätzliche Spalten mit lokaler Zeit ergänzen.

---

# ADR 003 – Persistenz & Datenhaltung (Parquet + Manifest)

## Status
Proposed

## Kontext
Die Pipeline erzeugt Artefakte auf mehreren Ebenen (`sensors`, `features`, `preds`, `metrics`).  
Für Reproduzierbarkeit und Nachvollziehbarkeit müssen diese konsistent gespeichert werden.  
Zur Diskussion standen: einfache Dateiausgabe (CSV/JSON), Datenbankintegration oder strukturierte Datei-Formate mit Metadaten.

## Entscheidung
- **Speicherformat:** Intern wird auf **Parquet** gesetzt (spaltenorientiert, komprimiert, schema-bewusst).  
- **Layering:** Trennung in *Bronze/Silver/Gold*:  
  - **Bronze:** normalisierte Rohsensorik (pro Sensor eine Datei).  
  - **Silver:** vorverarbeitete Sensorik (UTC-Index, resampled, bereinigt).  
  - **Gold:** Features & Predictions (modellfertig).  
- **Manifest:** Jeder Run erzeugt ein `manifest.json`, das Hashes, Config-Snapshot, Code-Versionen und Artefakt-Pfade dokumentiert.  
- **Metriken:** werden in `ctx.artifacts["metrics"]` gesammelt und als `metrics.json` persistiert.  
- **Run-ID:** wird pro Ausführung vergeben (z. B. Zeitstempel + Kurz-Hash); alle Artefakte landen in einem Run-Ordner.

## Begründung
- **Einfachheit:** Parquet ist leichtgewichtig, direkt mit Pandas nutzbar, benötigt keine DB-Server.  
- **Reproduzierbarkeit:** Manifest koppelt Input-Hash, Config und Output → Runs sind exakt nachvollziehbar.  
- **Erweiterbarkeit:** Optional kann später DuckDB oder MLflow/DVC auf den Parquet-Daten aufsetzen.  
- **Trennung:** Bronze/Silver/Gold folgt bewährten Data-Lake-Prinzipien, schafft klare Verantwortlichkeiten je Stage.

## Konsequenzen
- **Pro:** Reproduzierbarkeit ohne externe Infrastruktur, minimale Einstiegshürde.  
- **Pro:** Klare Trennung von Rohdaten, Preprocessing und Features → Debugging einfacher.  
- **Pro:** Erweiterbar Richtung MLflow/DVC, falls nötig.  
- **Contra:** Kein „always-on“-Abfrage-System (z. B. SQL-DB); Analysen laufen über Dateien.  
- **Mitigation:** Bei Bedarf wird eine Abfrage-Engine (DuckDB) ergänzt, ohne die Export-Logik zu ändern.

---

# ADR 004 – Windowing als eigene Stage M2.5

## Status
Accepted (implementiert 2025-12)

## Kontext
„Windowing“ (Zeitreihen in Segmente/Fenster schneiden) liegt zwischen PREPROCESS und FEATURES.  
Bisher ist es Teil der FEATURES-Stage (KISS für MVP).  
Für spätere Flexibilität (A/B-Vergleiche, Caching, App-Visualisierung) könnte eine eigene Stage sinnvoll sein.

## Entscheidung
- **Bis M2:** Windowing bleibt in FEATURES integriert.  
- **Ab M3:** Prüfung, ob eine eigene Stage **WINDOWING** eingeführt wird (PREPROCESS → WINDOWING → FEATURES).  
- Entscheidungskriterien: Wiederverwendbarkeit, Hyperparameter-Sweeps, App-Segmente, Caching/Export von Fenstern.

## Begründung
- **Pro:** Wiederverwendung, bessere Testbarkeit, Performance (einmal berechnen, mehrfach nutzen), App-UX (Segmente ohne Features darstellbar).  
- **Contra:** Mehr Contract (neue Ctx-Schublade `ctx.windows`), zusätzliche Tests, höhere Komplexität.

## Konsequenzen (falls aktiviert)
- Neues Feld `ctx.windows` (Schema: `window_id`, `start_utc`, `end_utc`, `center_utc`).  
- FEATURES konsumiert Fenster aus `ctx.windows` statt selbst zu schneiden.  
- Separate Tests für Windowing- und Feature-Schema.  
- Optional: Export von Fenster-Artefakten.

## Migrationspfad
1. Schema `ctx.windows` definieren.  
2. FEATURES auf `ctx.windows` umstellen.  
3. Tests anpassen (Windowing/Features trennen).  
4. Optional: Export ergänzen.  
5. Doku (README, Stage-Diagramm) aktualisieren.

## Offene Fragen
- Verknüpfung mit GPS (Center vs. Intervall)?  
- Distanz-/Geschwindigkeits-basierte Fenster statt Zeitfenster?  
- Export von Fenstern sofort nötig oder später?  

## Nächste Schritte
Dieses ADR wird zu Beginn von **M3 – Feature-Berechnung** erneut geprüft und finalisiert.  
Ergebnis (aktiviert/abgelehnt) wird hier mit Datum ergänzt.

---

# ADR 005 – Neue Ctx-Schublade `windows`

## Status
Accepted (Aktivierung ab M2.5)

## Kontext
Mit Einführung der Stage **WINDOWING** (zwischen PREPROCESS und FEATURES) entsteht eine neue Datenstruktur: Fensterdefinitionen.  
Bisher war unklar, ob diese direkt in `features` oder in `artifacts` abgelegt werden.  
Das Vermischen von Fenstergrenzen und Feature-Spalten führt jedoch zu semantischer Unschärfe.

## Entscheidung
~~`Ctx` erhält ein zusätzliches Feld `windows: Optional[pd.DataFrame]`.~~

**Update 2025-12:** Statt eines separaten `ctx.windows` Feldes wird das Windowing-Ergebnis direkt in `ctx.features["cluster"]` geschrieben. Dies vereinfacht die Architektur und vermeidet ein zusätzliches Ctx-Feld. Die WINDOW-Stage schreibt ein DataFrame mit `window_id`, `start_utc`, `end_utc`, `center_utc` nach `ctx.features`, das in der FEATURES-Stage erweitert wird.

- **WINDOWING** schreibt ein DataFrame mit den Spalten:  
  - `window_id` (int, eindeutig, lückenlos 0..N-1)  
  - `t_start_utc`, `t_end_utc` (UTC, monotone Grenzen)  
  - optional: `duration_s`, `coverage_*`, `n_samples_*`  
- **FEATURES** konsumiert dieses DataFrame und schreibt die eigentlichen Feature-Spalten in `ctx.features`.  
- Reservierte Spalten (`window_id`, `t_start_utc`, `t_end_utc`) werden unverändert übernommen.

## Begründung
- **Saubere Verantwortlichkeiten:** PREPROCESS → WINDOWING → FEATURES ohne Überschneidung.  
- **Testbarkeit:** getrennte Contracts für `windows` und `features`.  
- **Zukunftssicherheit:** später erweiterbar (z. B. zusätzliche Policies) ohne Umbau der Feature-Logik.  
- **Klarheit für Contributors:** Fenster ≠ Features → weniger Einstiegshürden.

## Konsequenzen
- Kleine Schemaänderung am `Ctx` (neues Feld).  
- Zusätzliche Tests für `ctx.windows` erforderlich.  
- Dokumentation und Diagramme (README, Stage-Übersicht) müssen angepasst werden.  
- Für den MVP reicht **ein einzelnes Fenster-DF**; Multi-Policy kann später via Erweiterung (`dict[str, DataFrame]` oder Policy-Spalte) ergänzt werden.

---

# ADR 006 – Rollen und Schreibrechte in Pipelines

## Status
Accepted

## Kontext
In der CtxPipeline werden alle Verarbeitungsschritte über `.add()` oder `.tap()` registriert.  
Die Engine unterscheidet **nicht** zwischen Transformern, Validatoren oder Reportern.  
Die Begriffe dienen ausschließlich der semantischen Einordnung und Dokumentation.

## Entscheidung
- Jeder `.add()`-Step arbeitet nach dem Vertrag `Ctx → Ctx` und besitzt immer ein `source` und ein `dest`.
- Ein Step darf **ausschließlich** in seinen definierten `dest` schreiben („kein Cross-Write“).
- `.tap()`-Steps sind strikt read-only und dürfen den `Ctx` nie verändern.
- Rollen sind **konventionell**, nicht technisch erzwungen:
  - **Transformer:** verändert Daten, schreibt z. B. in `"sensors"`.
  - **Validator:** prüft, gibt unverändertes Ziel zurück, wirft ggf. Exception.
  - **Reporter:** liest z. B. `"sensors"` und schreibt Ergebnisse nach `"artifacts"`.
- Validatoren und Reporter erfüllen denselben technischen Vertrag wie Transformer, unterscheiden sich nur durch ihre Side-Effect-Policy.

## Konsequenzen
- Keine Sonderlogik in der Pipeline-Engine nötig.
- Rollen-Disziplin wird über Namensschema, Docstrings und Tests gewährleistet.
- `artifacts` ist der einzige erlaubte Bereich für persistente Nebeninformationen (Metriken, Reports, Manifeste).

---

# ADR 007 – Parametrizable Steps (`fn_kwargs` + `with_kwargs`)

## Status
Accepted

## Kontext
In der bestehenden Pipeline können Funktionen (`fn`) nur mit festen Standardwerten verwendet werden.  
Für flexible und reproduzierbare Experimente ist es jedoch nützlich, beim Einhängen in die Pipeline Parameter zu überschreiben, ohne dafür separate Funktionsvarianten anzulegen.  

Bisher war das nur über `functools.partial` manuell möglich – jedoch uneinheitlich für dekorierte und undekorierte Funktionen.  
Da im Projekt nahezu alle Funktionsschritte durch `@transform_all_sensors` dekoriert sind, musste eine saubere, konsistente Lösung gefunden werden, **ohne** Pipeline- und Decorator-Schicht fest miteinander zu koppeln.

## Entscheidung
Es wird eine **zweistufige, aber einheitliche Schnittstelle** eingeführt:

1. **Pipeline-API (`fn_kwargs`):**  
   - `CtxPipeline.add(fn, *, source, dest=None, fn_kwargs=None)`  
   - `fn_kwargs` ist ein optionales `dict[str, Any]`, das ausschließlich **Keyword-Parameter** an `fn` bindet.  
   - Beim Hinzufügen prüft die Pipeline, ob alle Keys der Signatur von `fn` (oder einer kompatiblen Methode `with_kwargs`) entsprechen.  
   - Ungültige Keys führen zu einer **Exception beim Hinzufügen**, nicht erst zur Laufzeit.

2. **Parametrisierbare Steps (`with_kwargs`-Protokoll):**  
   - Decorators (z. B. `@transform_all_sensors`) können optional eine Methode  
     `with_kwargs(**kw)` bereitstellen, die einen neuen, angepassten Step zurückgibt.  
   - Wird eine solche Methode gefunden, nutzt die Pipeline sie anstelle von `functools.partial`.  
   - So bleibt die Notation für alle Funktionen **identisch**:  
     ```python
     pipe.add(step, source=["sensors"], dest="sensors", fn_kwargs={"x": 5})
     ```
   - Steps ohne `with_kwargs` werden automatisch per `partial(fn, **fn_kwargs)` behandelt.

## Begründung
- **Einheitlichkeit:** Ein API-Muster (`fn_kwargs`) für dekorierte und undekorierte Funktionen.  
- **Trennung der Schichten:** Die Pipeline kennt keine Decorator-Interna; sie prüft nur, ob `with_kwargs` existiert.  
- **Explizit statt magisch:** Decorators bieten `with_kwargs` freiwillig an, kein versteckter Vertrag.  
- **Frühe Fehlermeldungen:** Ungültige Keyword-Namen werden beim Hinzufügen erkannt.  
- **Reproduzierbarkeit:** Gebundene Parameter können ins Manifest/Logging aufgenommen werden.  
- **Kompatibilität:** Bestehende Pipelines und Decorators laufen unverändert weiter.

## Konsequenzen
- **Pro:** Einheitliche Parametrisierung ohne Infrastrukturkopplung.  
- **Pro:** Minimalinvasiv – Pipeline und Decorators bleiben unabhängig erweiterbar.  
- **Pro:** Klare Fehlermeldungen bei falschen Parametern, reproduzierbare Step-Labels (`func(x=5)` statt `functools.partial(...)`).  
- **Contra:** Leichter Mehraufwand bei Decorators, die Parametrisierung unterstützen wollen (`with_kwargs` muss einmalig implementiert werden).  
- **Mitigation:** Implementierung ist lokal in `sensors.py` möglich und vollständig testbar.

## Akzeptanzkriterien
- [x] `fn_kwargs` funktioniert für dekorierte **und** undekorierte Steps identisch.
- [x] Nur Keyword-Parameter erlaubt; ungültige Keys → Exception beim Hinzufügen.
- [x] Repr zeigt verständliche Step-Namen (`func(x=...)`).
- [x] `select(...).with_kwargs(...)` bleibt kompatibel und wirkt nur auf selektierte Sensoren.
- [x] Kein Zugriff der Pipeline auf `.core` oder andere Decorator-Interna.
- [x] Pipeline bleibt unverändert `Ctx → Ctx`; alle Steps sind weiterhin pure Functions.


> **Hinweis:**  
> Das gleiche Prinzip (`with_kwargs(**kw)`) kann analog in `@inspect_all_sensors` ergänzt werden.  
> Der Mechanismus ist identisch – Broadcast über Sensoren, Parametrisierung über gebundene Keyword-Argumente –  
> lediglich die Rückgabe bleibt `None` (Tap-Style). Keine Änderungen an der Pipeline nötig.

---

### ADR-008: Step Signature Policy

**Datum:** 2025-10-10  
**Status:** Accepted  
**Kontext:**
Die Transformation- und Inspektions-Decoratoren (`transform_all_sensors`, `inspect_all_sensors`) müssen wissen, wie sie Parameter an die zugrundeliegenden Funktionen binden.  
Um eine klare Trennung zwischen Datenfluss, Systemparametern und Konfigurationswerten zu gewährleisten, definieren wir verbindliche Regeln für Funktionssignaturen.


### Entscheidung

**Alle Step-Funktionen müssen folgende Struktur einhalten:**

| Kategorie | Beschreibung | Typ | Default | Beispiel |
|------------|---------------|------|----------|-----------|
| **Data Inputs** | Werte aus dem Ctx (z. B. `df`, `sensor_dfs`, `cfg`) | `POSITIONAL_OR_KEYWORD` | ❌ | `df: pd.DataFrame` |
| **Reserviert** | Systemparameter `sensor_name`, vom Decorator gesetzt | `KEYWORD_ONLY` | ❌ oder `None` (für Tests) | `*, sensor_name` |
| **Config/Tuning** | Überschreibbare Step-Konfigurationen | `KEYWORD_ONLY` | ✅ Pflicht | `gap_len: int = 3` |

Beispiel einer korrekten Signatur:
```python
def handle_nat_in_index(
    df: pd.DataFrame, *,
    sensor_name: str,
    gap_len: int = 3
) -> pd.DataFrame:
    ...
```

---

# ADR 009 – Dynamische Config-Erzeugung per Python-Prelayer

## Status
Accepted (Aktivierung ab M6)

## Kontext
Bisher wird eine statische `config.json` genutzt. Das ist reproduzierbar, aber unflexibel: keine Kommentare, keine ENV- oder CLI-Integration, keine Berechnungen.

## Entscheidung
Ein neuer **Prelayer (`.py`)** erzeugt vor jedem Run die finale JSON:
- Enthält eine Funktion `build_config(env, cli) -> dict`
- Kann ENV-Variablen, CLI-Parameter und Logik nutzen
- Erzeugt eine validierte, kanonische, gehashte JSON als einziges Input-Artefakt

`Ctx` speichert Pfad und Hash. Damit bleibt jede Run-Konfiguration eindeutig nachvollziehbar.

## Gründe
- Kommentare und Logik in der Config möglich
- ENV/CLI-Integration ohne Umwege
- Reproduzierbarkeit über den JSON-Hash gewährleistet
- JSON bleibt CI- und Tool-kompatibel

## Konsequenzen
- + Entwicklerkomfort, klare Trennung Logik/Artefakt
- + Reproduzierbarkeit durch Hash
- – zusätzlicher Build-Schritt, `.py` nur lokal erlaubt

## Beschluss
Ab **M6 – Engineering & Deployment** wird jede Pipeline-Config über einen `.py`-Generator erstellt und als deterministische `.json` im Run-Ordner persistiert.

## Betroffene Komponenten
`Ctx`, `PipelineRunner`, `ConfigValidator`, `CLI`, `Manifest`

---

## ADR010 – Einheitlicher Tap-Vertrag (dict-basiert, flatten/merge Policy)

**Datum:** 2025-11-01  
**Status:** Accepted  
**Kontext:**  
Die bisherige Tap-Implementierung übergab je nach Quelle entweder einzelne Objekte oder verschachtelte Dict-Strukturen an Inspectoren.  
Dadurch kam es zu Inkonsistenzen (z. B. doppelt verschachtelte `{"sensors": {"acc": ...}}`) und erschwertem Debugging.

**Entscheidung:**  
Alle `tap()`-Aufrufe liefern künftig **immer ein flaches `dict[str, Any]`** an den Inspector.  
Die Flatten-/Merge-Policy lautet:

- `source=str`  
  - Wenn das Ctx-Attribut bereits ein `dict` ist → **direkt durchreichen**.  
  - Wenn es ein Single-Objekt ist → in `{source: value}` einpacken.  
- `source=list`  
  - Alle Dict-Quellen werden **gemerged**.  
  - Alle Single-Quellen werden unter ihrem Namen eingefügt.  
  - Bei Key-Kollisionen wird der letzte Eintrag bevorzugt, eine Warnung wird ausgegeben.  
- `deepcopy=True` erzeugt eine tiefe Kopie des gesamten Dicts (Schutz vor Mutationen).  
- Rückgabewerte des Inspectors werden **ignoriert**, bei Rückgabe ≠ `None` erfolgt eine Warnung.

**Begründung:**  
- Einheitlicher Datenvertrag für alle Inspectoren.  
- Kein Spezialfall-Handling mehr bei „dict-Quellen“ (z. B. `sensors`).  
- Robuster gegenüber zukünftigen Multi-Source-Taps.  
- Klares, reproduzierbares Verhalten bei allen Stages.

**Alternativen:**  
- Beibehaltung des bisherigen Mixed-Verhaltens → führte zu schwer nachvollziehbaren Fehlern.  
- Typ-spezifische Pfade für einzelne Objektarten → unnötig komplex.  

**Ausblick:**  
- Optionale Erweiterung auf `Mapping`-Kompatibilität (statt reinem `dict`) möglich, wenn künftig auch andere Mapping-Typen (z. B. `OrderedDict`, `UserDict`) als Quellen auftreten.  
- Aktuell bleibt die interne Repräsentation bewusst `dict[str, Any]` für Einfachheit und Klarheit.


---


# ADR011 – Einführung eines Pipeline-Default-Mechanismus in CtxPipeline

**Datum:** 2025-11-02  
**Status:** geplant  
**Autor:** M. Neuhoff  
**Version:** Entwurf  

---

## 1) Entscheidung

In der CtxPipeline soll ein Mechanismus eingeführt werden, der es ermöglicht,
wiederkehrende Parameter (z. B. `source="sensors"`, `dest="features"`,
oder wiederholte `fn_kwargs={"cfg": ctx.config}`) einmalig pro Pipeline zu setzen.
Diese Werte gelten anschließend als **Default** für alle folgenden `.add()`- oder `.tap()`-Aufrufe.

---

## 2) Begründung

Der aktuelle Aufbau verlangt, dass in jeder Stage viele identische Parameter
immer wieder explizit angegeben werden müssen.
Dies ist redundant, fehleranfällig und behindert Lesbarkeit.

Ein per-Instanz definierter Default-Mechanismus reduziert Wiederholung,
erhält die explizite Kontrolle pro Pipeline und verändert keine bisherigen Verträge.

---

## 3) Entwurf (Kurzform)

Neue Methoden und Verhaltensregeln in `CtxPipeline`:

```python
class CtxPipeline:
    def __init__(self):
        self._defaults = {"source": None, "dest": None, "fn_kwargs": {}}
        self._steps = []

    def set_defaults(self, *, source=None, dest=None, fn_kwargs=None):
        if source is not None:
            self._defaults["source"] = source
        if dest is not None:
            self._defaults["dest"] = dest
        if fn_kwargs:
            self._defaults["fn_kwargs"] = {**self._defaults["fn_kwargs"], **fn_kwargs}

    def add(self, fn, *, source=None, dest=None, fn_kwargs=None):
        source_final = source or self._defaults["source"]
        dest_final = dest or self._defaults["dest"]
        merged_kwargs = {**self._defaults["fn_kwargs"], **(fn_kwargs or {})}
        self._steps.append((fn, source_final, dest_final, merged_kwargs))
        return self
```

- `.set_defaults()` legt Pipeline-weite Standardwerte fest.  
- `.add()` und `.tap()` mergen diese mit per-Call-Parametern (Call > Default).  
- Bereits registrierte Schritte bleiben unverändert, wenn Defaults später geändert werden.

---

## 4) Vorteile

- **KISS-Prinzip:** kein Framework-Magie, einfache Merge-Logik.
- **DRY-Prinzip:** deutlich weniger redundante Parameter in Stages.
- **Testbar:** Verhalten deterministisch und pro Instanz isoliert.
- **Kompatibel:** alle bestehenden Pipelines bleiben gültig.

---

## 5) Risiken und Gegenmaßnahmen

| Risiko | Beschreibung | Gegenmaßnahme |
|--------|---------------|---------------|
| Seiteneffekte durch Mutable Defaults | Änderung von `fn_kwargs` in place könnte alle Schritte beeinflussen | immer Kopie (`{**dict}`) anlegen |
| Intransparente Defaults | Entwickler sieht Defaults evtl. nicht sofort | Pipeline-Repräsentation zeigt *finale* Werte aller Steps |
| Spätere Subpipelines | mögliche doppelte Vererbung von Defaults | ADR011 nur für flache Pipelines, Sub-Defaults ggf. in ADR später |

---

## 6) Beispielverwendung

```python
def run_preprocess(ctx: "Ctx") -> "Ctx":
    p = CtxPipeline()
    p.set_defaults(source="sensors", fn_kwargs={"cfg": ctx.config})
    p.add(time_to_index)
    p.add(nan_handling, fn_kwargs={"method": "drop"})
    p.tap(print_info)
    return p(ctx)
```

---

## 7) Entscheidungskriterien

| Kriterium | Bewertung |
|------------|------------|
| Verständlichkeit | 🟢 sehr hoch |
| Code-Wiederverwendung | 🟢 verbessert |
| Abwärtskompatibilität | 🟢 voll |
| Komplexitätszuwachs | 🟡 gering |
| Wartbarkeit | 🟢 erhöht |

---

## 8) Status / Umsetzung

- [ ] Prototyp implementiert  
- [ ] Unit-Tests für Merge-Verhalten  
- [ ] Dokumentation im M6-Protokoll erstellt  
- [ ] Migration vorhandener Pipelines (`preprocess`, `features`, `window`) geplant  

---