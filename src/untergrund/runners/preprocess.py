from typing import Any, cast, Literal, Callable
from ..pipeline import CtxPipeline
from ..shared.inspect import show_sensor_details
from ..shared.sensors import transform_all_sensors
from ..context import Ctx
import pandas as pd
import numpy as np
from scipy.signal import butter, sosfiltfilt



### run preprocess Pipeline
def run_preprocess(ctx: "Ctx") -> "Ctx":
    pipeline = CtxPipeline()
    pipeline.add(time_to_index, source="sensors")
    pipeline.add(nan_handling, source="sensors", fn_kwargs={"method":"drop", "warn_threshold":0.01})
    pipeline.add(drop_columns, source="sensors", fn_kwargs={"columns_to_drop":["seconds_elapsed"]})
    pipeline.add(handle_nat_in_index, source="sensors", fn_kwargs={"gap_len":2})
    pipeline.add(sort_sensors_by_time_index, source="sensors")
    pipeline.add(group_duplicate_timeindex, source="sensors")
    pipeline.add(resample_imu_sensors.select(exclude=["Location", "Gyroscope"]), source="sensors", fn_kwargs={"cfg": ctx.config})
    pipeline.add(resample_imu_sensors.select(include=["Gyroscope"]), source="sensors", fn_kwargs={"cfg": ctx.config, "target_rate":100}) #später 50
    pipeline.add(resample_location_sensors.select(include=["Location"]), source="sensors", fn_kwargs={"cfg": ctx.config})
    pipeline.add(trim_to_common_timeframe, source="sensors", fn_kwargs={"cfg": ctx.config})
    pipeline.add(validate_basic_preprocessing, source="sensors")
    pipeline.add(high_pass_filter.select(include=["Accelerometer"]), source="sensors", fn_kwargs={"cfg": ctx.config})
    pipeline.add(high_pass_filter.select(include=["Gyroscope"]), source="sensors", fn_kwargs={"cfg": ctx.config})
    pipeline.tap(show_sensor_details, source="sensors")
    print("\nPipeline Repr:")
    print(pipeline)
    return pipeline(ctx)



### Zeitstempel -> Zeitindex
@transform_all_sensors
def time_to_index(df: pd.DataFrame, *, sensor_name:str | None = None, time_col:str="time") -> pd.DataFrame:
    """
    Wandelt 'time' Spalte (ns seit 1970-01-01 UTC) in DatetimeIndex um.
    - Erwartet Spalte time_col:str="time" in Nanosekunden.
    - Setzt Indexname auf 'time_utc' und Zeitzone auf UTC (tz-aware).
    """
    if df.empty:
        print(f"[Warning] DataFrame {sensor_name} is empty, nothing to index.")
        return df
    if time_col not in df.columns:
        raise ValueError(f"DataFrame {sensor_name} must contain a '{time_col}' column to convert to index.")

    df_time_index = df.copy()
    df_time_index.set_index(pd.to_datetime(df_time_index[time_col], unit="ns", utc=True, errors="coerce"), inplace=True)
    df_time_index.index.name = "time_utc"
    df_time_index.drop(columns=time_col, inplace=True)

    time_nans = df[time_col].isna().sum()
    time_nats = df_time_index.index.isna().sum()
    if time_nans != time_nats:
        print(f"[Warning] DataFrame {sensor_name}: {time_nans} NaN values in '{time_col}' column, but {time_nats} NaT values in index.")

    return df_time_index

@transform_all_sensors
def nan_handling(
    df: pd.DataFrame,
    *,
    sensor_name:str | None = None,
    warn_threshold: float = 0.05,
    method: Literal["drop", "ffill", "bfill"] = "ffill"
) -> pd.DataFrame:
    """
    Entfernt oder füllt NaN-Werte eines DataFrames basierend auf der angegebenen Methode:
      - "drop" = Zeilen mit NaN löschen
      - "ffill" = vorwärts, dann rückwärts füllen
      - "bfill" = rückwärts, dann vorwärts füllen
    """
    # TODO: config unterstützung implementieren

    sum_nans = df.isna().sum().sum()
    size = df.size

    # Ausgaben
    if sum_nans == 0:
        print(f"[Info] DataFrame {sensor_name} has no NaN values. No handling needed.")
        return df
    else:
        print(f"[Info] DataFrame {sensor_name} contains {sum_nans} NaN values. -> Applying {method} to handle them.")
    if sum_nans / size > warn_threshold:
        print(f"[Warning] DataFrame {sensor_name} has more than {warn_threshold * 100}% NaN values ({sum_nans} NaNs in {size} total).")

    # TODO: längere gaps erkennen und warnen
    # TODO: ggf. intelligente Methodik verwenden
   
    # Methoden
    handlers: dict[str, Callable] = {
        "drop":   lambda x: x.dropna(),
        "ffill":  lambda x: x.fillna(method="ffill").fillna(method="bfill"),
        "bfill":  lambda x: x.fillna(method="bfill").fillna(method="ffill"),
    }
    # ist die Methode zulässig?
    allowed = set(handlers.keys())
    if method not in allowed:
        raise ValueError(f"Unknown NaN handling method: {method}. Allowed methods: {allowed}")
    
    # handling
    return handlers[method](df)
    

### Bestimmte Spalten entfernen
@transform_all_sensors
def drop_columns(df: pd.DataFrame, *, sensor_name:str | None = None, columns_to_drop:list[str]|None=None) -> pd.DataFrame:
    """
    Entfernt bestimmte Spalten aus jedem Sensor-DataFrame.
    - Standardmäßig wird die Spalte "seconds_elapsed" entfernt.
    TODO: Config unterstützung einbauen
    """
    columns_to_drop = columns_to_drop or ["seconds_elapsed"]
    if df.empty:
        print(f"[Warning] DataFrame {sensor_name} is empty, nothing to drop.")
        return df
    df_out = df.copy()
    
    existing_cols_set = set(df_out.columns)
    columns_to_drop_set = existing_cols_set & set(columns_to_drop)
    expected_cols_count = len(existing_cols_set - columns_to_drop_set)
    # drop
    df_out.drop(columns=columns_to_drop_set, errors="ignore", inplace=True)
    if len(set(df_out.columns)) == 0:
        print(f"[Warning] DataFrame {sensor_name} has no columns left after dropping {columns_to_drop}.")
    if len(set(df_out.columns)) != expected_cols_count:
        print(f"[Warning] DataFrame {sensor_name}: Expected {expected_cols_count} columns after dropping, but got {len(df_out.columns)}.")
    return df_out

### NaT Handling
@transform_all_sensors
def handle_nat_in_index(df: pd.DataFrame, *, sensor_name:str | None = None, gap_len:int = 3) -> pd.DataFrame:
    """
    Zählt NaT im Index, erkennt zusammenhängende NaT-Cluster (in Samples) und dropt NaT-Zeilen.
    Warnung, wenn ein Cluster >= gap_len Samples umfasst.
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError(f"DataFrame {sensor_name} index must be a DatetimeIndex")
    
    if not df.index.hasnans:
        print(f"[Info] DataFrame {sensor_name} has no NaT values in index. Returning original DataFrame.")
        return df
        
    nat_series = pd.Series(df.index.isna(), index=df.index) #Pandas Series statt numpy Array, damit groupby funktioniert
    nat_count = int(nat_series.sum())
    print(f"[Warning] DataFrame {sensor_name} index contains {nat_count} NaT values. Initial shape: {df.shape}")
    
    # Zusammenhängende NaT-Cluster erkennen
    switch_points = (nat_series != nat_series.shift()) # Wert mit vorherigem Wert (shift()) vergleichen -> wechselpunkte zwischen True/False
    group_id = switch_points.cumsum() # kumulative Summe der Wechselpunkte -> Gruppen-ID
    group_sizes = nat_series.groupby(group_id).sum() # größe der true-Gruppen zählen (False-Gruppen sind 0)  
    if gap_len < 1:
        raise ValueError("gap_len must be >= 1")
    gap_count = int((group_sizes >= gap_len).sum()) 
    
    # Warnung bei langem NaT-Cluster
    if gap_count > 0:
        longest_gap = int(group_sizes.max())
        print(f"[Warning] DataFrame {sensor_name} found {gap_count} NaT blocks with length >= {gap_len}! longest={longest_gap}.")
        
    # Entfernen der NaT-Zeilen
    df_cleaned = df[~nat_series]
    print(f"[Info] DataFrame {sensor_name} removed {nat_count} NaT rows, resulting shape: {df_cleaned.shape}")
    if df_cleaned.shape[0] != df.shape[0] - nat_count:
        print(f"[Warning] DataFrame {sensor_name}: After removing NaT rows, expected {df.shape[0] - nat_count} rows but got {df_cleaned.shape[0]} rows.")
    return df_cleaned
    
        


### Sortieren der Sensoren nach Zeitstempel
@transform_all_sensors
def sort_sensors_by_time_index(df: pd.DataFrame, *, sensor_name:str | None = None) -> pd.DataFrame:
    """
    Sortiert DataFrame nach Zeitindex (DatetimeIndex, aufsteigend, stabil).

    - Prüft Typ, Duplikate und NaT im Index.
    - Sortiert nur, wenn nicht bereits monoton aufsteigend.
    - Reihenfolge bei gleichen Zeitstempeln bleibt erhalten.
    - NaT-Werte werden ans Ende verschoben.
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError(f"DataFrame {sensor_name} index must be a DatetimeIndex")
    
    # vor dem Sortieren prüfen
    rows_in_df = df.shape[0]
    if rows_in_df == 0:
        print(f"[Warning] DataFrame {sensor_name} is empty, nothing to sort.")
        return df # leeres DF
    if df.index.is_monotonic_increasing:
        print(f"[Info] DataFrame {sensor_name} is already sorted by time index.")
        return df # schon sortiert
    if df.index.has_duplicates:
        print(f"[Warning] DataFrame {sensor_name} index has duplicate time entries.")
    if df.index.hasnans:
        nat_count = df.index.isna().sum()
        print(f"[Warning] DataFrame {sensor_name} index contains {nat_count} NaT values.")

    # Sortieren
    df_sorted = df.sort_index(na_position="last", kind="stable") # stabil = Reihenfolge bei gleichen Zeitstempeln bleibt erhalten
    print(f"[Info] DataFrame {sensor_name} sorted by time index.")

    return df_sorted

### Gruppieren von doppelten Zeitstempeln
@transform_all_sensors
def group_duplicate_timeindex(df: pd.DataFrame , *, sensor_name:str | None = None) -> pd.DataFrame:
    """
    Gruppiert Zeilen mit gleichen Zeitstempeln.
    zählt alle auftretenden Gruppen.
        - Numerische Spalten: Median (später werden evtl. noch andere Aggregationsmethoden implementiert)
        - Nicht-numerische Spalten (inklusive bool): Erster Wert
        - NaT-Zeilen werden dedupliziert. (...sollten am besten vorher schon entfernt werden)
    Gibt einen DataFrame mit eindeutigen Zeitstempeln zurück.
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError(f"DataFrame {sensor_name} index must be a DatetimeIndex")
    
    if df.index.has_duplicates:
        rows_in = df.shape[0]
        dup_timestamps = df.index.duplicated(keep="first")
        print(f"[Info] DataFrame {sensor_name}: {dup_timestamps.sum()} duplicate timestamps found")
        rows_out = rows_in - dup_timestamps.sum()
        print(f"[Info] DataFrame {sensor_name}: estimated: reducing rows from {rows_in} to {rows_out}")

        # Anzahl Gruppen
        count_groups = df.index[dup_timestamps].nunique()
        print(f"[Info] DataFrame {sensor_name}: {count_groups} unique duplicate timestamp groups found")

        # Gruppen bilden getrennt nach numerischen und nicht-numerischen Spalten
        df_numeric = pd.DataFrame(index=df.index)
        df_not_numeric = pd.DataFrame(index=df.index)
        df_grouped = pd.DataFrame(index=df.index.unique()) # neuer DF mit eindeutigen Zeitstempeln in alter Reihenfolge
        num_cols = df.select_dtypes(include='number').columns
        non_num_cols = df.select_dtypes(exclude='number').columns
        if not num_cols.empty:
            df_numeric = df[num_cols]
            df_numeric_grouped = df_numeric.groupby(df.index,dropna=False).median()
        else:
            df_numeric_grouped = pd.DataFrame(index=df.index.unique())
        if not non_num_cols.empty:
            df_not_numeric = df[non_num_cols]
            df_not_numeric_grouped = df_not_numeric.groupby(df.index,dropna=False).first()
        else:
            df_not_numeric_grouped = pd.DataFrame(index=df.index.unique())
        
        # konkatinieren der gruppierten DataFrames
        df_grouped = pd.concat([df_numeric_grouped, df_not_numeric_grouped], axis=1)
        df_grouped = df_grouped[df.columns]  # Spaltenreihenfolge beibehalten
        df_grouped.index.name = df.index.name  # Indexname beibehalten

        # kurze Validierung
        if not df_grouped.index.is_monotonic_increasing:
            print(f"[Warning] Grouped DataFrame {sensor_name}: index is not sorted!")
        rows_removed = rows_in - df_grouped.shape[0]
        if not rows_removed == dup_timestamps.sum():
            print(f"[Warning] Grouped DataFrame {sensor_name}: removed {rows_removed} rows, but expected to remove {dup_timestamps.sum()} rows!")
        if not df_grouped.shape[0] == rows_out:
            print(f"[Warning] Grouped DataFrame {sensor_name}: has {df_grouped.shape[0]} rows, expected {rows_out} rows!")

        print(f"[Info] Grouped DataFrame {sensor_name}: all columns grouped, resulting shape: {df_grouped.shape}")
        return df_grouped
    
    else:
        print(f"[Info] DataFrame {sensor_name}: No duplicate timestamps found, no grouping needed.")
        return df
    
### Validierung der Basisfunktionen des Preprocessings
@transform_all_sensors
def validate_basic_preprocessing(df: pd.DataFrame, *, sensor_name: str) -> pd.DataFrame:
    """
    Führt eine Reihe von Validierungen auf dem DataFrame durch:
    - Prüft, ob der Index ein DatetimeIndex ist.
    - Prüft, ob der Index monoton aufsteigend ist.
    - Prüft, ob der Index Duplikate enthält.
    - Prüft, ob der Index NaT-Werte enthält.
    - Prüft, ob der Index eine Zeitzone hat und ob diese UTC ist.
    - Gibt Warnungen aus, wenn der DataFrame leer ist, sehr wenig Daten hat, oder keine Spalten hat.
    - Setzt den Indexnamen auf 'time_utc', wenn er einen anderen Namen hat. + Info    
    Gibt den unveränderten DataFrame zurück, wenn alle Prüfungen bestanden sind.
    """
    # harte Fehler
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError(f"DataFrame '{sensor_name}' index must be a DatetimeIndex")

    if df.index.tz is None:
        raise ValueError(f"DataFrame '{sensor_name}' index must be timezone-aware")

    if str(df.index.tz) != "UTC":
        raise ValueError(f"DataFrame '{sensor_name}' index must be in UTC timezone")
    
    if df.index.hasnans:
        nat_count = df.index.isna().sum()
        raise ValueError(f"DataFrame '{sensor_name}' index contains {nat_count} NaT values")

    if not df.index.is_monotonic_increasing:
        raise ValueError(f"DataFrame '{sensor_name}' index is not monotonically increasing")

    if df.index.has_duplicates:
        dup_count = df.index.duplicated().sum()
        raise ValueError(f"DataFrame '{sensor_name}' index has {dup_count} duplicate time entries")

    # Index Namen setzen
    if df.index.name != "time_utc":
        old_name = df.index.name
        df.index.name = "time_utc"
        print(f"[Info] Index name was {old_name} until now! -> Set index name to 'time_utc'")

    # Warnungen
    if df.empty:
        print(f"[Warning] Sensor '{sensor_name}' is empty.")
    if df.shape[0] < 10:
        print(f"[Info] Sensor '{sensor_name}' has only {df.shape[0]} rows, very little data.")
    if df.shape[1] == 0:
        print(f"[Warning] Sensor '{sensor_name}' has no columns.")

    print(f"[Info] DataFrame '{sensor_name}' passed all basic preprocessing validations.")
    return df   

### Resample IMU Sensoren auf einheitliche Abtastrate
@transform_all_sensors
def resample_imu_sensors(df: pd.DataFrame, *, cfg: dict[str, Any] | None = None, target_rate: int = 100, agg_func: Literal["mean","median","first","last"] = "mean", interp_method: Literal["linear","time","nearest","pad"] = "time") -> pd.DataFrame:
    """
    Alle IMU-Sensoren auf eine einheitliche Abtastrate resamplen.
    -> Nicht-numerische Spalten werden entfernt
    - target_rate: Zielabtastrate in Hz
    - agg_func: Aggregationsmethode für Resampling
        - mean: Mittelwert
        - median: Median
        - first: Erster Wert
        - last: Letzter Wert
    - interp_method: Interpolationsmethode für fehlende Werte nach Resampling
        - linear: lineare Interpolation
        - time: zeitbasierte Interpolation
        - nearest: nächster Wert
        - pad: vorheriger Wert (Vorwärtsfüllung)
    * cfg optional: Konfigurationsdictionary, um Parameter zu überschreiben
    """
    # Nur numerische Spalten weiterverarbeiten (restliche Spalten gehen verloren!)
    df = df.select_dtypes(include="number")
    # Parameter aus config laden, falls vorhanden -> fallback auf Default-Parameter
    if cfg and "resample_imu" in cfg:
        target_rate = cfg["resample_imu"].get("target_rate", target_rate)
        agg_func = cfg["resample_imu"].get("agg_func", agg_func)
        interp_method = cfg["resample_imu"].get("interp_method", interp_method)
    else:
        print("[Info] No 'resample_imu' config found, using default parameters.")
    # von Hz in ms
    step = pd.to_timedelta(1 / target_rate, unit='s')
    # Resampling
    out = df.resample(step, origin="epoch", label="left", closed="left").agg(agg_func)
    if interp_method == "pad":
        out = out.interpolate(method="pad", limit=None, limit_direction="forward") # type: ignore[arg-type] #checker kennt 'pad' nicht
    else:
        out = out.interpolate(method=interp_method, limit=None, limit_direction="both")
    # erste Zeile kann NaN enthalten, wenn der erste Zeitstempel nicht genau auf das Resample-Ziel fällt -> entfernen
    if out.iloc[0].isna().all():
        out = out.iloc[1:]
    return out

### Resample Location Sensoren auf einheitliche Abtastrate
@transform_all_sensors
def resample_location_sensors(df: pd.DataFrame, *, cfg: dict[str, Any] | None = None, target_rate: int = 1, fill_method: Literal["ffill", "nearest"] = "ffill", limit: int | None = None) -> pd.DataFrame:
    """
    Alle Location-Sensoren auf eine einheitliche Abtastrate resamplen.
    -> Nicht-numerische Spalten werden entfernt!
    - target_rate: Zielabtastrate in Hz
    - fill_method: Methode zum Auffüllen fehlender Werte nach Resampling
        - ffill: Vorwärtsfüllung (forward fill)
        - nearest: nächster Wert
    * cfg optional: Konfigurationsdictionary, um Parameter zu überschreiben
    """
    # Nur numerische Spalten weiterverarbeiten (restliche Spalten gehen verloren!)
    df = df.select_dtypes(include="number")
    # Parameter aus config laden, falls vorhanden -> fallback auf Default-Parameter
    if cfg and "resample_location" in cfg:
        target_rate = cfg["resample_location"].get("target_rate", target_rate)
        fill_method = cfg["resample_location"].get("fill_method", fill_method)
        limit = cfg["resample_location"].get("limit", limit)
    else:
        print("[Info] No 'resample_location' config found, using default parameters.")
    # von Hz in ms
    step = pd.to_timedelta(1 / target_rate, unit='s')
    # Resampling
    if fill_method == "ffill":
        out = df.resample(step, origin="epoch", label="left", closed="left").ffill(limit=limit)
    elif fill_method == "nearest":
        out = df.resample(step, origin="epoch", label="left", closed="left").nearest(limit=limit)
    else:
        raise ValueError(f"Unknown aggregation method: {fill_method}")
    # erste Zeile kann NaN enthalten, wenn der erste Zeitstempel nicht genau auf das Resample-Ziel fällt -> entfernen
    if out.iloc[0].isna().all():
        out = out.iloc[1:]
    return out


### Auf einheitlichen Start/Ende trimmen
# keine @transform_all_sensors, da alle Sensoren zusammen betrachtet werden müssen
def trim_to_common_timeframe(sensors_dict: dict[str, pd.DataFrame], *, cfg: dict[str, Any] | None = None, align_to_sensor: str | None = None,warn_if_cut_seconds: int | None = None) -> dict[str, pd.DataFrame]:
    """
    Trimmt alle Sensoren auf den gemeinsamen Zeitrahmen.
    - Findet den spätesten Startzeitpunkt und den frühesten Endzeitpunkt aller Sensoren.
    - Schneidet alle Sensoren auf diesen gemeinsamen Zeitraum zu.
    - align_to_sensor: Optionaler Sensorname, an den alle anderen Sensoren angepasst werden. Sonst Gemeinsamer Zeitraum über alle Sensoren.
    - Gibt Warnungen aus "warn_if_cut_seconds" Sekunden oder länger abgeschnitten wird.
    - Es wird davon ausgegangen, dass alle DataFrames:
        - einen DatetimeIndex haben
        - sortiert sind
        - keine Duplikate im Index haben
        - monoton aufsteigend sind
        - keine NaT-Werte im Index haben
         -> NaT-Werte werden bis zum nächsten validen Timestamp übersprungen (ggf. simple variante mit df.index[0])
    """
    if not isinstance(sensors_dict, dict):
        raise ValueError("sensors_dict must be a dictionary")
    if not all(isinstance(df, pd.DataFrame) for df in sensors_dict.values()):
        raise ValueError("All values in sensors_dict must be DataFrames")
    if any(df.empty for df in sensors_dict.values()):
        raise ValueError("At least one DataFrame in sensors_dict is empty")
    ## Soft Variante: leere Sensoren ignorieren
    # empty_sensors = [name for name, df in sensors_dict.items() if df.empty]
    # if empty_sensors:
    #     print(f"[Warning] Empty sensors found: {empty_sensors}")
    ##
    if not all(isinstance(df.index, pd.DatetimeIndex) for df in sensors_dict.values()):
        raise ValueError("All DataFrames in sensors_dict must have a DatetimeIndex")

    # Parameter aus config laden, falls vorhanden -> fallback auf Default-Parameter
    if cfg and "trim_to_common_timeframe" in cfg:
        align_to_sensor = cfg["trim_to_common_timeframe"].get("align_to_sensor", align_to_sensor)
        warn_if_cut_seconds = cfg["trim_to_common_timeframe"].get("warn_if_cut_seconds", warn_if_cut_seconds)    
    else:
        print("[Info] No 'trim_to_common_timeframe' config found, using default parameters.")


    # Start und Ende bestimmen
    def first_last_indices(d: dict[str, pd.DataFrame]) -> tuple[list[pd.Timestamp], list[pd.Timestamp], pd.Timestamp | None, pd.Timestamp | None]:
        """Liste aller ersten und letzten Indizes der DataFrames, sowie den frühesten und spätesten Zeitpunkt insgesamt."""
        first_indices = [cast(pd.Timestamp, idx) for df in d.values() if (idx := df.first_valid_index()) is not None and isinstance(idx, pd.Timestamp)] # ggf. simple variante mit df.index[0] implemenrieren... performace und so...
        last_indices = [cast(pd.Timestamp, idx) for df in d.values() if (idx := df.last_valid_index()) is not None and isinstance(idx, pd.Timestamp)]
        earliest = min(first_indices) if first_indices else None
        latest = max(last_indices) if last_indices else None
        return first_indices, last_indices, earliest, latest

    def common_start_end(d: dict[str, pd.DataFrame]) -> tuple[pd.Timestamp | None, pd.Timestamp | None, pd.Timestamp | None, pd.Timestamp | None]:
        """Findet den frühesten gemeinsamen Start- und den spätesten gemeinsamen Endzeitpunkt der DataFrames."""
        first_indices , last_indices, earliest, latest = first_last_indices(d)
        start = max(first_indices) if first_indices else None
        end = min(last_indices) if last_indices else None
        return start, end, earliest, latest

    def start_end_align_to_sensor(d: dict[str, pd.DataFrame], ats: str) -> tuple[pd.Timestamp | None, pd.Timestamp | None, pd.Timestamp | None, pd.Timestamp | None]:
        """Findet den Start- und Endzeitpunkt des angegebenen Sensors"""
        if not ats:
            raise ValueError("align_to_sensor is None, but required for this function.")
        if ats not in d:
            raise KeyError(f"align_to_sensor '{ats}' not found in sensors_dict.")
        
        s = d[ats].first_valid_index()
        e = d[ats].last_valid_index()
        start = cast(pd.Timestamp, s) if isinstance(s, pd.Timestamp) else None
        end = cast(pd.Timestamp, e) if isinstance(e, pd.Timestamp) else None
        _, _, earliest, latest = first_last_indices(d)
        return start, end, earliest, latest
    
    if align_to_sensor:
        start, end, earliest, latest = start_end_align_to_sensor(sensors_dict, align_to_sensor)
    else:
        start, end, earliest, latest = common_start_end(sensors_dict)

    if start is None or end is None:
        raise ValueError("Start or end is None -> cannot trim sensors.")
    if start > end:
        raise ValueError("Start time > end time -> cannot trim sensors.")
    
    # Warnung, wenn viel abgeschnitten wird
    if warn_if_cut_seconds is not None and earliest is not None and latest is not None:
        trimmed_from_start = (start - earliest).total_seconds()
        trimmed_from_end = (latest - end).total_seconds()
        if trimmed_from_start >= warn_if_cut_seconds:
            print(f"[Warning] Trimming {trimmed_from_start} seconds from the start.")
        if trimmed_from_end >= warn_if_cut_seconds:
            print(f"[Warning] Trimming {trimmed_from_end} seconds from the end.")

    # zuschneiden aller Sensoren
    return {sensor_name: sensor_df.loc[start:end].copy() for sensor_name, sensor_df in sensors_dict.items()} # copy(), nur zur sicherheit


### High-Pass Filter
@transform_all_sensors
def high_pass_filter(df: pd.DataFrame,
                    *,
                    sensor_name: str | None = None,
                    cfg: dict[str, Any] | None = None,
                    cutoff_freq: float = 2,
                    sample_rate: float = 100.0,
                    order: int = 4,
                    include_columns: list[str] | None = None
                    ) -> pd.DataFrame:
    """
    Wendet einen Hochpassfilter auf alle oder ausgewählte numerischen Spalten des DataFrames an.
    Wir gehen davon aus:
    - keine NaN-Werte (oder Inf-Werte) im DataFrame
    - keine duplikate im Index
    - monoton aufsteigender DatetimeIndex
    - gleichmäßige Abtastrate (sample_rate)
    - cutoff_freq > 0, sample_rate > 0, order >= 1
    - Grenzfrequenz in einem soliden Bereich (0.02 < wn < 0.8)
    """
    # TODO: Samplerate ermitteln statt als parameter übergeben! (index diff sollte konstant sein)

    # Parameter aus config laden, falls vorhanden -> fallback auf Default-Parameter
    if cfg and sensor_name in cfg.get("hp_filters", {}):
        sensor_cfg = cfg["hp_filters"][sensor_name]
        cutoff_freq = sensor_cfg.get("cutoff_freq", cutoff_freq)
        sample_rate = sensor_cfg.get("sample_rate", sample_rate)
        order = sensor_cfg.get("order", order)
        include_columns = sensor_cfg.get("include_columns", include_columns)
        
    # Normalisierte Grenzfrequenz berechnen
    wn = cutoff_freq / (sample_rate/2)

    # Voraussetzungen prüfen
    if not 0.02 <= wn <= 0.8:
        raise ValueError(f"Normalized cutoff frequency wn={wn} out of valid range.")
    pad_len = 3 * (order + 1)  # Padding-Länge für filtfilt
    if df.shape[0] < pad_len:
        raise ValueError(f"DataFrame {sensor_name} has too few samples ({df.shape[0]}) for filtering. Reduce order or resample to higher sample_rate. (len(df) < 3 * (order + 1))")
    if df.isna().any().any():
        raise ValueError(f"DataFrame {sensor_name} contains NaN values. Please handle them before applying the high-pass filter.")

    # Zu filternde Spalten auswählen
    if include_columns is None:
        df_to_filter = df.select_dtypes(include="number").astype("float64").copy() # alle numerischen Spalten
    else:
        if not all(col in df.columns for col in include_columns):
            missing_cols = [col for col in include_columns if col not in df.columns]
            raise ValueError(f"DataFrame {sensor_name} is missing columns for high-pass filter: {missing_cols}")
        num_cols = df[include_columns].select_dtypes(include="number").columns
        if len(num_cols) != len(include_columns):
            raise ValueError(f"DataFrame {sensor_name}: include_columns contains non-numerical columns.")
        df_to_filter = df[include_columns].astype("float64").copy() # nur angegebene Spalten

    # prüfen, ob noch Spalten zum Filtern übrig sind
    if df_to_filter.empty:
            raise ValueError(f"DataFrame {sensor_name} has no more numerical columns to apply the high-pass filter.")
    
    # Filter erstellen und anwenden
    sos = butter(order, wn, btype='highpass', output='sos')
    filtered = sosfiltfilt(sos, df_to_filter.to_numpy(), axis=0)

    # Plausibilitätscheck
    if not np.isfinite(filtered).all():
        print(f"[WARNING] {sensor_name}: Filtering produced non-finite values (NaN/Inf).")
    # TODO: weitere Plausibilitätschecks:
    # - Mittelwerte vor/nach Filterung vergleichen -> nahe 0?
    # - Varianzen vor/nach Filterung vergleichen -> Varianz kleiner?
    # - Spalten nahezu konstant? -> Parameter anpassen?

    # Ergebnis zusammenbauen
    hp_df = df.copy()
    hp_df[df_to_filter.columns] = filtered
    return hp_df