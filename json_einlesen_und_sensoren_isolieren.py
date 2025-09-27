import marimo

__generated_with = "0.15.2"
app = marimo.App(width="columns")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""## Imports""")
    return


@app.cell
def imports():
    import marimo as mo
    import pandas as pd
    import numpy as np
    import re
    import copy as _cpy

    from scipy.signal import butter, filtfilt, freqz
    import matplotlib.pyplot as plt

    from dataclasses import dataclass, field
    from enum import Enum, auto
    from functools import wraps
    from typing import Callable, Any, Iterable, Protocol, Optional
    from inspect import signature
    return (
        Any,
        Callable,
        Enum,
        Iterable,
        Optional,
        Protocol,
        auto,
        dataclass,
        field,
        mo,
        pd,
        re,
        signature,
        wraps,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""## Globale Variablen""")
    return


@app.cell
def _():
    # Dateiname der Quell-Datei als JSON
    DATA = "testdaten.json"
    # Auswahl der Sensoren die man verwenden möchte
    SENSOR_LIST = ["Accelerometer","Gyroscope","GameOrientation","Location"]
    return DATA, SENSOR_LIST


@app.cell
def _(
    Callable,
    Stage,
    run_export,
    run_features,
    run_ingest,
    run_local_classify,
    run_preprocess,
    run_select,
):
    STAGE_FUNCS: dict["Stage", Callable[["Ctx"], "Ctx"]] = {
        Stage.INGEST: run_ingest,
        Stage.SELECT: run_select,
        Stage.PREPROCESS: run_preprocess,
        Stage.FEATURES: run_features,
        Stage.LOCAL_CLASSIFY: run_local_classify,
        Stage.EXPORT: run_export,
    }
    return (STAGE_FUNCS,)


@app.cell
def _(Enum, auto):
    class Stage(Enum):
        """Feste Stages. Reihenfolge wie deklaiert."""
        INGEST = auto()          # Einlesen, Sensor-Dict bauen, Metadata extrahieren
        SELECT = auto()          # gewünschte Sensoren filtern, fehlende melden
        PREPROCESS = auto()      # Zeitindex/UTC, Cleaning, Resample, etc.
        FEATURES = auto()        # Windowing (zuerst) + Feature-Berechnung
        LOCAL_CLASSIFY = auto()  # Klassifikation innerhalb der einen Fahrt (ML)
        EXPORT = auto()          # Artefakte persistieren (Features,,Preds, Config, etc.)
    return (Stage,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""## Allgemeine Funktionen / Klassen""")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""Simple "start"-Funktion um die Stages zu druchlaufen""")
    return


@app.cell
def _(STAGE_FUNCS: "dict['Stage', Callable[['Ctx'], 'Ctx']]", Stage):
    def run_stages(ctx: "Ctx") -> "Ctx":
        for st in Stage:
            ctx = STAGE_FUNCS[st](ctx) 
        return ctx
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""Die Funktionen, welche hinterher die Pipelines enthalten werden für jede Stage""")
    return


@app.cell
def _():
    def run_ingest(ctx: "Ctx") -> "Ctx":
        print("[INGEST]")
        return ctx

    def run_select(ctx: "Ctx") -> "Ctx":
        print("[SELECT]")
        return ctx

    def run_preprocess(ctx: "Ctx") -> "Ctx":
        print("[PREPROCESS]")
        return ctx

    def run_features(ctx: "Ctx") -> "Ctx":
        print("[FEATURES]")
        return ctx

    def run_local_classify(ctx: "Ctx") -> "Ctx":
        print("[LOCAL_CLASSIFY]")
        return ctx

    def run_export(ctx: "Ctx") -> "Ctx":
        print("[EXPORT]")
    return (
        run_export,
        run_features,
        run_ingest,
        run_local_classify,
        run_preprocess,
        run_select,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
    Der Folgende Decorator macht Funktionen die sonst nur auf einzelen Objekte anwendbar sind auch auf alle Objekte als Value innerhalb eines Dictionarys anwendbar. Da wir die Sonsordaten je Sensor in getrennten Sensor_DFs und diese als Dict[name,Senor_DF] verarbeiten, können wir Funktionen sowohl auf einzelne Sonsoren wie auch eine Sammlung von Senoren in einem Dict anwenden.

    Sollte der Dict-Key, also der Sensor-Name, benötigt werden wird dieser als kwarg="sensor_name" übergeben. gibt es kein kwarg="sensor_name" wird dieser auch nicht übergeben.
    """
    )
    return


@app.cell
def _(Callable, Iterable, Protocol, re, signature, wraps):
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


    def apply_to_all_sensors[T](func: Callable[[T], T]) -> SensorStep[T]:
        """
        Decorator: Macht aus einer Input->Output Funktion eine,
        die auch dict[str, Input] -> dict[str, Output] versteht.
        Falls die Funktion ein Argument `sensor_name` akzeptiert,
        wird der Dict-Key automatisch als 'sensor_name' übergeben.
        Zusätzlich gibt es die Mathode .select(...), um die Funktion nur auf
        bestimmte Keys im Dict anzuwenden.
        """

        accepts_name = "sensor_name" in signature(func).parameters

        def apply(name: str | None, value: T) -> T:
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
                    selective_wrapper.__name__ = f"select({getattr(func,'__name__','func')})"
                    return out
                else:
                    return apply(None, x)

            return selective_wrapper

        setattr(wrapper, "select", select)  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]
    return (apply_to_all_sensors,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
    Kontext Objekt für die Pipeline:

    - enthält alle Daten für den gesamten Ablauf
    """
    )
    return


@app.cell
def _(Any, Optional, dataclass, field, pd):
    @dataclass(frozen=True, slots=True)
    class Ctx:
        """
        Context-Objekt für die MVP-Pipeline (eine Fahrt, lokale Klassifikation).

        Enthält nur die nötigsten Daten:
          - sensors:   Zeitreihen pro Sensor (kein "Metadata")
          - meta:      globale Fahrtinfos (aus "Metadata"-Sensor extrahiert)
          - features:  Fenster-Features (nur Input-Merkmale + Schlüsselspalten)
          - preds:     Vorhersagen/Labels je Fenster (gefüllt in LOCAL_CLASSIFY)
          - config:    Lauf-Parameter (z. B. Fenstergröße, Resample-Takt, Seeds)
          - artifacts: Provenienz (run_id, Pfade, Hashes), KEINE großen Objekte

        frozen=True  → unveränderlich, Änderungen nur über dataclasses.replace
        slots=True   → feste Attribute, weniger Speicher, keine "zufälligen" Felder
        """
        sensors: dict[str, pd.DataFrame] = field(default_factory=dict)
        meta: dict[str, Any] = field(default_factory=dict)

        features: Optional[pd.DataFrame] = None
        preds: Optional[pd.Series] = None

        config: dict[str, Any] = field(default_factory=dict)
        artifacts: dict[str, Any] = field(default_factory=dict)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""Die folgende Klasse deint als Pipeline um Funktionen auf in gewählter Reihenfolge anwenden zu können.""")
    return


@app.cell
def _(Callable, Iterable):
    class Pipeline[T]:
        """
        Mini-Pipeline für Sensor-Daten.
        - Führe mehrere Funktionen nacheinander aus
        - Callable: pipe(data) als Aufruf (wie eine Funktion)
        - Repräsentation zeigt die Steps: Pipeline: step1 → step2 → step3
        """

        def __init__(self, steps: Iterable[Callable[[T], T]] | None = None):
            self.steps: list[Callable[[T], T]] = []
            self.taps: dict[str, list[object]] = {}  # Rückgaben von Tap-Funktionen (optional)
            # Konstruktor einheitlich über add:
            if steps:
                for f in steps:
                    self.add(f)

        def __call__(self, x: T) -> T:
            """Wendet alle Steps nacheinander auf x an und gibt das Endergebnis zurück."""
            for f in self.steps:
                x = f(x)
                if x is None: #Fehler werfen falls eine Funktion der Pipeline keinen return hat.
                    raise RuntimeError(f"Step {getattr(f, '__name__', repr(f))} hat nichts zurückgegeben!")
            return x

        def __repr__(self) -> str:
            if not self.steps:
                return "Pipeline: (empty)"
            names = [getattr(f, "__name__", repr(f)) for f in self.steps]
            numbered = [f"{i:02} → {name}" for i, name in enumerate(names, start=1)]
            return "Pipeline:\n  " + "\n  ".join(numbered)

        def add(self, f: Callable[[T], T]) -> "Pipeline[T]":
            """Hängt einen Step hinten an (Chaining möglich)."""
            self.steps.append(f)
            return self

        def tap(self, fn: Callable[[T], object]) -> "Pipeline[T]":
            """Hängt eine Inspektionsfunktion an.
            - führt fn(x) aus (Side-Effect)
            - gibt x unverändert weiter!!!
            - speichert fn-Return (falls != None) in self.taps[fn.__name__]
            tap ruft intern add auf!
            """
            name = getattr(fn, "__name__", "lambda")

            def wrapper(x: T) -> T:
                x_copy = _cpy.deepcopy(x)      # Safety first – keine Mutation am Original
                result = fn(x_copy)            
                if result is not None:
                    self.taps.setdefault(name, []).append(result)
                return x # Original geht zurück in die Pipeline

            wrapper.__name__ = f"tap({name})"
            return self.add(wrapper) 
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""## Daten einlesen und als Dict [Sensorname, DataFrame] bereitstellen""")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""JSON --> DF""")
    return


@app.cell
def _(pd):
    def read_json(data) -> pd.DataFrame:
        try:
            df = pd.read_json(f"data/{data}")
        except:
            raise RuntimeError(f"JSON kann nicht eingelesen werden (data/{data})")
        if "sensor" not in df.columns:
            print("keine Sensoren im DF")
        return df
    return (read_json,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
    Dict mit key=Sensor, Value=DF(Values des Sensors) -> Alle NAN-Spalten löschen -> Index zurücksetzen
    (Metadaten werden als "Sensor" geführt)
    """
    )
    return


@app.cell
def _(pd):
    def build_sensor_dict(df:pd.DataFrame) -> dict[str,pd.DataFrame]:
        return {sensor: grouped_dfs.dropna(axis=1, how="all").reset_index(drop=True) for sensor, grouped_dfs in df.groupby("sensor")}
    return (build_sensor_dict,)


@app.cell
def _(DATA, build_sensor_dict, read_json):
    df = read_json(DATA)
    sensor_dfs = build_sensor_dict(df)
    return (sensor_dfs,)


@app.cell
def _(Any, pd):
    def extract_metadata(sensor_dfs: dict[str, pd.DataFrame]) -> dict[str, Any]:
        meta = {}
        if "Metadata" in sensor_dfs:
            meta = sensor_dfs["Metadata"].iloc[0].to_dict()
        else:
            print("keine Metadaten vorhanden!?")
        return meta
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""## Sensor anhand der globalen SENSOR_LIST auswählen.""")
    return


@app.cell
def selected_sensors(pd):
    # Auswahl der Senoren als selected_sensors
    def select_sensors(sensor_dfs: dict[str, pd.DataFrame], sensor_list: list[str]) -> dict[str, pd.DataFrame]:
        selected_sensors = {sensor: data for sensor, data in sensor_dfs.items() if sensor in sensor_list}
        missing_sensors = [s for s in sensor_list if s not in selected_sensors]
        if missing_sensors:
            print(f"Folgende Sensoren fehlen in der Aufnahme: {missing_sensors}")
        return selected_sensors
    return (select_sensors,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""selected_sensors als Startpunkt für die Pipeline""")
    return


@app.cell
def _(SENSOR_LIST, select_sensors, sensor_dfs):
    selected_sensors = select_sensors(sensor_dfs, SENSOR_LIST)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""## Transformations Funktionen für die Pipeline:""")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""### Zeit als Index setzen""")
    return


@app.cell
def _(apply_to_all_sensors, pd):
    @apply_to_all_sensors
    def time_to_index(df: pd.DataFrame) -> pd.DataFrame:
        df_timeindex = df.copy()
        df_timeindex.set_index(pd.to_datetime(df_timeindex["time"], unit="ns", utc=True),inplace=True)
        df_timeindex.index.name = "time_utc"
        df_timeindex.drop(columns="time", inplace=True)
        # später auf richtige reihenfolge der Zeitstempel, Duplikate und Lücken prüfen
        return df_timeindex
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""## Ausgabe/Inspektions Funktionen für die Pipeline:""")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""### Sensor Details anzeigen:""")
    return


@app.cell
def _(apply_to_all_sensors, pd):
    #Daten der Sensoren zur Überprüfung sichten
    @apply_to_all_sensors
    def show_sensor_details(sensor: pd.DataFrame, *, sensor_name:str) -> pd.DataFrame:
        print(f"{sensor_name:<20} {len(sensor):>10} Messpunkte {sensor.isna().sum().sum():>10} NaNs")
        return sensor
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r""" """)
    return


if __name__ == "__main__":
    app.run()
