from typing import Any

import pandas as pd

from ..context import Ctx
from ..pipeline import CtxPipeline, bridge


### run ingest Pipeline

def run_ingest(ctx: "Ctx") -> "Ctx":
    sensors_step = bridge(
        lambda cfg: cfg["input_path"],
        read_json,
        build_sensor_dict,
        name="config->sensors",
    )

    pipeline = (
        CtxPipeline()
        .add(sensors_step, source="config", dest="sensors")
        .add(extract_metadata, source="sensors", dest="meta")
        .add(drop_metadata_sensor, source="sensors")
    )
    return pipeline(ctx)


### JSON --> DF

def read_json(path) -> pd.DataFrame:
    ''' Liest eine JSON-Datei ein und gibt sie als DataFrame zurueck.'''
    try:
        df = pd.read_json(path)
    except Exception:
        raise RuntimeError(f"JSON kann nicht eingelesen werden ({path})")
    if "sensor" not in df.columns:
        print("keine Sensoren im DF")
    return df


### DF --> Dict[Sensor, DF]

def build_sensor_dict(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    '''Dict mit key=Sensor, Value=DF(Values des Sensors)
        -> Alle NAN-Spalten loeschen
        -> Index zuruecksetzen
        (Metadaten werden als "Sensor" gefuehrt)
    '''
    return {
        str(sensor): grouped_dfs.dropna(axis=1, how="all").reset_index(drop=True)
        for sensor, grouped_dfs in df.groupby("sensor")
    }


### Dict[Sensor["Metadata"], DF] --> Dict[Meta]

def extract_metadata(sensor_dfs: dict[str, pd.DataFrame]) -> dict[str, Any]:
    '''Extrahiert die Metadaten aus dem Sensor-DF-Dict.
       Gibt ein Dict mit den Metadaten zurueck.
       Wenn keine Metadaten vorhanden sind, wird ein leeres Dict zurueckgegeben.
    '''
    meta = {}
    if "Metadata" in sensor_dfs:
        meta = sensor_dfs["Metadata"].iloc[0].to_dict()
    else:
        print("keine Metadaten vorhanden!?")
    return meta


def drop_metadata_sensor(sensors: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    '''Entfernt den Sensor "Metadata" aus dem Sensors-Dict (falls vorhanden).'''
    if "Metadata" in sensors:
        return {k: v for k, v in sensors.items() if k != "Metadata"}
    return sensors
