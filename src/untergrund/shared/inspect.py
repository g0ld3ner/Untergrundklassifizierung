
from typing import cast, Optional
import pandas as pd
from ..shared.sensors import inspect_all_sensors


### Zeilen, Spalten, NaNs, Frequenz pro Sensor ausgeben
@inspect_all_sensors
def row_col_nan_dur_freq(sensor: pd.DataFrame, *, sensor_name: str) -> None:
    '''TAP FUNKTION: Gibt Details zu jedem Sensor als Tabelle aus.'''
    # Alternative Frequenzschätzung, falls pd.infer_freq nicht inferieren kann
    def estimate_freq_alternative(index: pd.DatetimeIndex, exact: bool = False) -> str:
        if len(index) < 2:
            return "Not inferable"
        deltas = index.to_series().diff().dt.total_seconds().dropna()
        deltas = deltas[deltas > 0]
        if deltas.empty:
            return "Not inferable"
        freq = 1.0 / deltas.median()
        if exact:
            return f" {freq:.2f} Hz"
        return f" ~{freq:.2f} Hz"

    row, col = sensor.shape
    nan_count = sensor.isna().sum().sum()
    dur_delta = (max(sensor.index) - min(sensor.index))
    dur = str(dur_delta).split()[-1].split(".")[0].strip()
    # print(f"[Debug] DataFrame {sensor_name} index is Type = {type(sensor.index)}")
    try:
        infer_freq = pd.infer_freq(cast(pd.DatetimeIndex, sensor.index))
    except TypeError:
        infer_freq = None
        freq = "not DatetimeIndex"
    else:
        if infer_freq is None and isinstance(sensor.index, pd.DatetimeIndex):
            freq = estimate_freq_alternative(sensor.index)
        elif isinstance(infer_freq, str):
            try:
                seconds = pd.Timedelta(infer_freq).total_seconds()
                freq = 1.0 / seconds if seconds > 0 else "not inferable"
                freq = f" {freq:.2f} Hz" if isinstance(freq, float) else freq
            except ValueError: # pd.infer_freq kann auch nur die Zeiteinheit (z.b. s, D, etc.) zurückgeben -> fallback auf estimate_freq_alternative
                # freq = f" {infer_freq}" # alternativ einfach die infer_freq ausgeben
                freq = estimate_freq_alternative(sensor.index, exact=True) # type: ignore -> sensor.index muss DatetimeIndex sein # wir wissen, das hier das Ergebniss Exakt ist
        else:
            freq = "not inferable"

    print("++" + "-"*22 + "+" + "-"*16 + "+" + "-"*16 + "+" + "-"*16 + "+" + "-"*17 + "+" + "-"*26 + "++")
    print(f"||  {sensor_name:<20}|  rows={row:>7}  |  cols={col:>7}  |  NaNs={nan_count:>7}  |  dur={dur:>9}  |  freq={freq:<17}  ||")
    print("++" + "-"*22 + "+" + "-"*16 + "+" + "-"*16 + "+" + "-"*16 + "+" + "-"*17 + "+" + "-"*26 + "++")
    return None

@inspect_all_sensors
def head_tail(sensor: pd.DataFrame, *, sensor_name: str, n: int = 3) -> None:
    '''TAP FUNKTION: Gibt die ersten und letzten n=3 Zeilen jedes Sensors aus.'''
    len_name = len(sensor_name) + 20
    print(f"===== Sensor: {sensor_name} =====")
    print(sensor.head(n))
    print(sensor.tail(n))
    print("-"*len_name)
    return None

@inspect_all_sensors
def print_info(sensor: pd.DataFrame, *, sensor_name: str) -> None:
    '''TAP FUNKTION: Gibt info() zu jedem Sensor aus.'''
    len_name = len(sensor_name) + 20
    print(f"===== Sensor: {sensor_name} =====")
    print(sensor.info())
    print("-"*len_name)
    return None

@inspect_all_sensors
def print_description(sensor: pd.DataFrame, *, sensor_name: str) -> None:
    '''TAP FUNKTION: Gibt describe() zu jedem Sensor aus.'''
    len_name = len(sensor_name) + 20
    print(f"===== Sensor: {sensor_name} =====")
    print(sensor.describe())
    print("-"*len_name)
    return None

@inspect_all_sensors
def start_end(sensor: pd.DataFrame, *, sensor_name: str) -> None:
    '''TAP FUNKTION: Gibt Start- und Endzeitpunkt jedes Sensors aus.'''
    start = str(sensor.index[0])
    end = str(sensor.index[-1])
    length = str(sensor.index[-1] - sensor.index[0]).split()[-1].strip()
    print(f"Sensor: {sensor_name:<20} Start= {start:<37} Ende= {end:<37} Länge= {length}")
    return None

