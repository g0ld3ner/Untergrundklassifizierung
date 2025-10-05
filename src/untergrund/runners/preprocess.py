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
def time_to_index(df: pd.DataFrame) -> pd.DataFrame:
    df_timeindex = df.copy()
    if "time" not in df_timeindex.columns:
        raise ValueError("DataFrame must contain a 'time' column to convert to index.")
    df_timeindex.set_index(pd.to_datetime(df_timeindex["time"], unit="ns", utc=True),inplace=True)
    df_timeindex.index.name = "time_utc"
    df_timeindex.drop(columns="time", inplace=True)
    return df_timeindex


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