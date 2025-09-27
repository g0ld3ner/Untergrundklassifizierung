from typing import Any
from ..context import Ctx
from ..pipeline import CtxPipeline
import pandas as pd

### run select Pipeline
def run_select(ctx: "Ctx") -> "Ctx":
    pipeline = CtxPipeline()
    pipeline.add(select_sensors, source=["sensors", "config"], dest="sensors")
    return pipeline(ctx)

### Sensoren auswählen
def select_sensors(sensor_dfs: dict[str, pd.DataFrame], cfg: dict[str, Any]) -> dict[str, pd.DataFrame]:
    '''Wählt die Sensoren aus sensor_dfs aus, die in sensor_list angegeben sind.'''
    sensor_list = cfg.get("sensor_list", [])
    selected_sensors = {sensor: data for sensor, data in sensor_dfs.items() if sensor in sensor_list}
    missing_sensors = [s for s in sensor_list if s not in selected_sensors]
    if missing_sensors:
        print(f"Folgende Sensoren fehlen in der Aufnahme: {missing_sensors}")
    return selected_sensors