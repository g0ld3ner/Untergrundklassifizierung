from src.untergrund.context import Ctx
from untergrund.shared.inspect import start_end, print_description, print_info, head_tail, row_col_nan_dur_freq
from ..pipeline import CtxPipeline
import pandas as pd
import numpy as np

# zwingend als erstes im RUNNER ausführen!
def select_window_key(ctx: "Ctx", window_key: str="default") -> str:
    """Setzt den globalen Fenster-Schlüssel für die Feature-Funktionen"""
    windows_dict = ctx.features
    if len(windows_dict) == 0:
        raise ValueError("No feature sets available to set as global.")
    if len(windows_dict) == 1:
        key = next(iter(windows_dict))
        print(f"Only one feature set available. Using the only key: '{key}'")
        return key
    if window_key in windows_dict:
        print(f"Multiple feature sets available. Using specified key: '{window_key}'")
        return window_key   
    raise ValueError(f"Multiple feature sets available, but specified key '{window_key}' not found in windows.")

# RUNNER
def run_features(ctx: "Ctx") -> "Ctx":
    w_key = select_window_key(ctx, "cluster") # <<-- window_key für die Pipeline-Funktionen setzen
    # Richtige Spalten im Window-DataFrame?
    required = {"start_utc", "end_utc"}
    if not required.issubset(ctx.features[w_key].columns):
        raise ValueError(f"Im Window-DataFrame '{w_key}' müssen {required} Spalten vorhanden sein.")
    # Feature-Pipeline aufbauen
    pipeline = CtxPipeline()
    # Deafault Werte für Feature-Funktionen setzen
    def add_f(fn, **kwargs):
        """add_Features Wrapper um defaults zu setzen -> wird später Globales Pipelinefeature"""
        pipeline.add(fn, source=["sensors","features"], dest="features", fn_kwargs={"window_key": w_key, **kwargs})
    
    # Features hinzufügen:
    add_f(acc_rms)

    pipeline.tap(row_col_nan_dur_freq, source="features")
    pipeline.tap(head_tail, source="features")
    pipeline.tap(print_info, source="features")
    pipeline.tap(print_description, source="features")
    pipeline.tap(start_end, source="features")


    print("\nFeature-Pipeline Repr:")
    print(pipeline)
    return pipeline(ctx)

def acc_rms(sensors: dict[str, pd.DataFrame], features: dict[str, pd.DataFrame], *, window_key: str, sensor_name: str = "Accelerometer", cols: list[str] = ["x", "y", "z"]) -> dict[str, pd.DataFrame]:
    """Calculate the RMS of acceleration values in the given window."""
    if sensor_name not in sensors:
        raise ValueError(f"Sensor '{sensor_name}' not found in sensors dict.")
    
    fdf = features[window_key].copy()
    acc = sensors[sensor_name]

    missing_cols = [c for c in cols if c not in acc.columns]
    if missing_cols:
        raise ValueError(f"[acc_rms] Im Sensor '{sensor_name}' fehlen Spalten: {missing_cols}")
    
    rms_values = []
    nan_count = 0
    for i, row in fdf.iterrows(): #ggf. später ohne das "kostbare" iterrows() implementieren
        start_utc = row["start_utc"]
        end_utc = row["end_utc"]
        window_data = acc.loc[(acc.index >= start_utc) & (acc.index < end_utc), cols]
        if len(window_data) == 0:
            rms_values.append(np.nan)
            nan_count += 1
            continue
        rms = np.sqrt((window_data**2).sum().sum() / len(window_data))
        rms_values.append(rms)
        
    if nan_count > 0:
        print(f"[Warning] acc_rms: {nan_count} windows had no data and resulted in NaN RMS values.")    

    fdf["acc_rms"] = rms_values
    return {**features, window_key: fdf}