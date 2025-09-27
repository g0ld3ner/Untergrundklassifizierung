from ..context import Ctx
import pandas as pd
from typing import Any

### run ingest Pipeline
def run_ingest(ctx: "Ctx") -> "Ctx":
    print("+++INGEST+++") # Platzhalter für die Pipeline
    return ctx

### JSON --> DF
def read_json(data) -> pd.DataFrame:
    ''' Liest eine JSON-Datei ein und gibt sie als DataFrame zurück.'''
    try:
        df = pd.read_json(f"data/{data}")
    except:
        raise RuntimeError(f"JSON kann nicht eingelesen werden (data/{data})")
    if "sensor" not in df.columns:
        print("keine Sensoren im DF")
    return df

### DF --> Dict[Sensor, DF]
def build_sensor_dict(df:pd.DataFrame) -> dict[str,pd.DataFrame]:
    '''Dict mit key=Sensor, Value=DF(Values des Sensors)
        -> Alle NAN-Spalten löschen
        -> Index zurücksetzen
        (Metadaten werden als "Sensor" geführt)
    '''
    return {str(sensor): grouped_dfs.dropna(axis=1, how="all").reset_index(drop=True) for sensor, grouped_dfs in df.groupby("sensor")}

### Dict[Sensor["Metadata"], DF] --> Dict[Meta]
def extract_metadata(sensor_dfs: dict[str, pd.DataFrame]) -> dict[str, Any]:
    '''Extrahiert die Metadaten aus dem Sensor-DF-Dict.
       Gibt ein Dict mit den Metadaten zurück.
       Wenn keine Metadaten vorhanden sind, wird ein leeres Dict zurückgegeben.
    '''
    meta = {}
    if "Metadata" in sensor_dfs:
        meta = sensor_dfs["Metadata"].iloc[0].to_dict()
    else:
        print("keine Metadaten vorhanden!?")
    return meta


# --- Ingest via CtxPipeline (KISS) ---
from ..pipeline import CtxPipeline


def read_json(path: str) -> pd.DataFrame:
    """Liest eine JSON-Datei ein und gibt sie als DataFrame zurück."""
    df = pd.read_json(path)
    if "sensor" not in df.columns:
        raise RuntimeError("Ingest: Spalte 'sensor' fehlt im JSON-DataFrame.")
    return df


def ingest_sensors(cfg: dict[str, Any]) -> dict[str, pd.DataFrame]:
    path = cfg["input_path"]
    df = read_json(path)
    return build_sensor_dict(df)


def derive_meta_from_sensors(sensors: dict[str, pd.DataFrame]) -> dict[str, Any]:
    return extract_metadata(sensors)


def run_ingest(ctx: "Ctx") -> "Ctx":
    pipe = (
        CtxPipeline()
        .add(ingest_sensors, source="config", dest="sensors", name="ingest_sensors")
        .add(derive_meta_from_sensors, source="sensors", dest="meta", name="extract_metadata")
    )
    return pipe(ctx)

