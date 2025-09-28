from ..pipeline import CtxPipeline
from ..shared.inspect import show_sensor_details
from ..shared.sensors import apply_to_all_sensors
from ..context import Ctx
import pandas as pd

### run preprocess Pipeline
def run_preprocess(ctx: "Ctx") -> "Ctx":
    pipeline = CtxPipeline()
    pipeline.add(time_to_index, source="sensors", dest="sensors")
    pipeline.tap(show_sensor_details, source="sensors")
    return pipeline(ctx)


@apply_to_all_sensors
### Zeitstempel -> Zeitindex
def time_to_index(df: pd.DataFrame) -> pd.DataFrame:
    df_timeindex = df.copy()
    df_timeindex.set_index(pd.to_datetime(df_timeindex["time"], unit="ns", utc=True),inplace=True)
    df_timeindex.index.name = "time_utc"
    df_timeindex.drop(columns="time", inplace=True)
    # später auf richtige reihenfolge der Zeitstempel, Duplikate und Lücken prüfen --> eigene Funktion?
    return df_timeindex