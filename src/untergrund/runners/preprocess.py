from ..pipeline import CtxPipeline
from ..shared.inspect import show_sensor_details
from ..shared.sensors import transform_all_sensors
from ..context import Ctx
import pandas as pd

### run preprocess Pipeline
def run_preprocess(ctx: "Ctx") -> "Ctx":
    pipeline = CtxPipeline()
    pipeline.add(time_to_index, source="sensors", dest="sensors")
    pipeline.tap(show_sensor_details, source="sensors")
    return pipeline(ctx)



### Zeitstempel -> Zeitindex
@transform_all_sensors
def time_to_index(df: pd.DataFrame, time_col:str="time") -> pd.DataFrame:
    """
    Wandelt 'time' Spalte (ns seit 1970-01-01 UTC) in DatetimeIndex um.
    - Erwartet Spalte time_col:str="time" in Nanosekunden.
    - Setzt Indexname auf 'time_utc' und Zeitzone auf UTC (tz-aware).
    """
    if df.empty:
        print("[Warning] DataFrame is empty, nothing to index.")
        return df
    if time_col not in df.columns:
        raise ValueError(f"DataFrame must contain a '{time_col}' column to convert to index.")
    
    df_time_index = df.copy()
    df_time_index.set_index(pd.to_datetime(df_time_index[time_col], unit="ns", utc=True, errors="coerce"), inplace=True)
    df_time_index.index.name = "time_utc"
    df_time_index.drop(columns=time_col, inplace=True)

    time_nans = df[time_col].isna().sum()
    time_nats = df_time_index.index.isna().sum()
    if time_nans != time_nats:
        print(f"[Warning] {time_nans} NaN values in '{time_col}' column, but {time_nats} NaT values in index.")

    return df_time_index

### NaT Handling
@transform_all_sensors
def handle_nat_in_index(df: pd.DataFrame, gap_len:int = 3) -> pd.DataFrame:
    """
    Zählt NaT im Index, erkennt zusammenhängende NaT-Cluster (in Samples) und dropt NaT-Zeilen.
    Warnung, wenn ein Cluster >= gap_len Samples umfasst.
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("DataFrame index must be a DatetimeIndex")
    
    if not df.index.hasnans:
        print("[Info] No NaT values found in index. Returning original DataFrame.")
        return df
        
    nat_series = pd.Series(df.index.isna(), index=df.index) #Pandas Series statt numpy Array, damit groupby funktioniert
    nat_count = int(nat_series.sum())
    print(f"[Warning] DataFrame index contains {nat_count} NaT values. Initial shape: {df.shape}")

    
    
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
        print(f"[Warning] Found {gap_count} NaT blocks with length >= {gap_len}! longest={longest_gap}.")
        
    # Entfernen der NaT-Zeilen
    df_cleaned = df[~nat_series]
    print(f"[Info] Removed {nat_count} NaT rows, resulting shape: {df_cleaned.shape}")
    if df_cleaned.shape[0] != df.shape[0] - nat_count:
        print(f"[Warning] After removing NaT rows, expected {df.shape[0] - nat_count} rows but got {df_cleaned.shape[0]} rows.")
    return df_cleaned
    
        


### Sortieren der Sensoren nach Zeitstempel
@transform_all_sensors
def sort_sensors_by_time_index(df: pd.DataFrame) -> pd.DataFrame:
    """
    Sortiert DataFrame nach Zeitindex (DatetimeIndex, aufsteigend, stabil).

    - Prüft Typ, Duplikate und NaT im Index.
    - Sortiert nur, wenn nicht bereits monoton aufsteigend.
    - Reihenfolge bei gleichen Zeitstempeln bleibt erhalten.
    - NaT-Werte werden ans Ende verschoben.
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("DataFrame index must be a DatetimeIndex")
    
    # Checks before sorting
    rows_in_df = df.shape[0]
    if rows_in_df == 0:
        print("[Warning] DataFrame is empty, nothing to sort.")
        return df  # Nothing to sort
    if df.index.is_monotonic_increasing:
        print("[Info] DataFrame is already sorted by time index.")
        return df  # Already sorted
    if df.index.has_duplicates:
        print("[Warning] DataFrame index has duplicate time entries.")
    if df.index.hasnans:
        nat_count = df.index.isna().sum()
        print(f"[Warning] DataFrame index contains {nat_count} NaT values.")
    
    # Perform sorting
    df_sorted = df.sort_index(na_position="last", kind="stable") # Stable sort -> relative order of equal elements
    print("[Info] DataFrame sorted by time index.")

    return df_sorted

### Gruppieren von doppelten Zeitstempeln
@transform_all_sensors
def group_duplicate_timeindex(df: pd.DataFrame) -> pd.DataFrame:
    """
    Gruppiert Zeilen mit gleichen Zeitstempeln.
    zählt alle auftretenden Gruppen.
        - Numerische Spalten: Median
        - Nicht-numerische Spalten (inklusive bool): Erster Wert
        - NaT-Zeilen werden dedupliziert. 
    Gibt einen DataFrame mit eindeutigen Zeitstempeln zurück.
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("DataFrame index must be a DatetimeIndex")
    
    if df.index.has_duplicates:
        rows_in = df.shape[0]
        dup_timestamps = df.index.duplicated(keep="first")
        print(f"[Info] {dup_timestamps.sum()} duplicate timestamps found")
        rows_out = rows_in - dup_timestamps.sum()
        print(f"[Info] estimated: reducing rows from {rows_in} to {rows_out}")

        # Anzahl Gruppen
        count_groups = df.index[dup_timestamps].nunique()
        print(f"[Info] {count_groups} unique duplicate timestamp groups found")

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
            print("[Warning] Grouped DataFrame index is not sorted!")
        rows_removed = rows_in - df_grouped.shape[0]
        if not rows_removed == dup_timestamps.sum():
            print(f"[Warning] Grouped DataFrame removed {rows_removed} rows, but expected to remove {dup_timestamps.sum()} rows!")
        if not df_grouped.shape[0] == rows_out:
            print(f"[Warning] Grouped DataFrame has {df_grouped.shape[0]} rows, expected {rows_out} rows!")

        print(f"[Info] all columns grouped, resulting shape: {df_grouped.shape}")
        return df_grouped
    
    else:
        print("[Info] No duplicate timestamps found, no grouping needed.")
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