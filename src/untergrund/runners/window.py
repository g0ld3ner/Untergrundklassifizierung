from typing import Any
from ..context import Ctx
from ..pipeline import CtxPipeline
from ..shared.inspect import row_col_nan_dur_freq, head_tail, print_info, print_description, start_end
import pandas as pd

def run_window(ctx: "Ctx") -> "Ctx":
    pipeline = CtxPipeline()
    pipeline.add(windowing,source="sensors", dest="features", fn_kwargs={"cfg": ctx.config, "window_key": "cluster"})
    pipeline.tap(row_col_nan_dur_freq, source="features")
    pipeline.tap(head_tail, source="features")
    pipeline.tap(print_info, source="features")
    pipeline.tap(print_description, source="features")
    pipeline.tap(start_end, source="features")
    return pipeline(ctx)

def windowing(sensors: dict[str, pd.DataFrame], *, cfg: dict[str, Any], duration_s: int = 4, hop_s: int = 2, window_key: str = "default") -> dict[str, pd.DataFrame]:
    """
    Erzeugt Fenster-DataFrame basierend auf t-min/t-max aller Sensoren.
    - Index: fortlaufender Integer (window_id)
    - Je eine Spalte für Start-, End- und Mittelpunkt-Zeitstempel.
    Args:
        sensors: Dict von Sensor-Zeitreihen (DataFrames mit DatetimeIndex)
        cfg: Konfig-Dict (duration_s/hop_s)
        duration_s: Fenster-Länge in Sekunden 
        hop_s: Fenster-Abstand in Sekunden, Überlappung möglich und ggf. gewünscht
        -> duration_s sollte ein Vielfaches von hop_s sein, sonst bekommt man unregelmäßige Überlappungen.
    Returns:
        pd.DataFrame mit Fenster-Informationen (start_utc, end_utc, center_utc)
    """
    # Konfig werte laden
    if cfg.get("window_duration_s") is not None:
        duration_s = cfg["window_duration_s"]
        print(f"[Info] Using configured window_duration_s={duration_s}s")
    else:
        print(f"[Info] Using default window_duration_s={duration_s}s")
    if cfg.get("window_hop_s") is not None:
        hop_s = cfg["window_hop_s"]
        print(f"[Info] Using configured window_hop_s={hop_s}s")
    else:
        print(f"[Info] Using default window_hop_s={hop_s}s")

    # param checks
    if sensors is None or len(sensors) == 0:
        raise ValueError("sensors dict is empty or None")
    if not all(len(df) > 0 for df in sensors.values()):
        raise ValueError("All sensor DataFrames must have at least one row")
    if not all(isinstance(df.index, pd.DatetimeIndex) for df in sensors.values()):
        raise ValueError("All sensor DataFrames must have a DatetimeIndex")
    if duration_s <= 0 or hop_s <= 0:
        raise ValueError("duration_s and hop_s must be positive values")
    if hop_s > duration_s:
        raise ValueError("hop_s must be less than or equal to duration_s")
    if duration_s % hop_s != 0:
        print(f"[Warning] duration should be a multiple of hop for consistent windowing.")
    
    
    # gemeinsame Zeitspanne aller Sensoren ermitteln (sollte vorher eigentlich schon getrimmt sein)
    t_min: pd.Timestamp = min(df.index.min() for df in sensors.values())
    t_max: pd.Timestamp = max(df.index.max() for df in sensors.values())
    time_range: pd.DatetimeIndex = pd.date_range(start = t_min, end = t_max - pd.Timedelta(duration_s, 's'), freq=pd.Timedelta(hop_s, unit='s'))

    # t min/max checks
    if t_min >= t_max:
        raise ValueError("Invalid sensor data: t_min >= t_max")
    if duration_s > (t_max - t_min).total_seconds():
        raise ValueError("duration_s is larger than the total time range of the sensor data")
    
    # Fenster-DataFrame erstellen
    window_df = pd.DataFrame()
    window_df.index = time_range 
    window_df["start_utc"] = window_df.index
    window_df["end_utc"] = window_df.index + pd.Timedelta(duration_s, unit='s')
    window_df["center_utc"] = window_df.index + pd.Timedelta(duration_s / 2, unit='s')
    window_df.index.name = "window_id"
    window_df.reset_index(drop=True, inplace=True) # index als fortlaufenden Integer("window_id")

    # letztes Fenster  droppen, wenn es unvollständig ist
    window_df = window_df[window_df["end_utc"] <= t_max]
    print(f"[Info] Created {len(window_df)} windows from {t_min} to {t_max} with duration {duration_s}s and hop {hop_s}s.")
    # TODO: Struktur des window_df gegenüber der Erwartung prüfen
    return {window_key: window_df}