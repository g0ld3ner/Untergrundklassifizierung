
import pandas as pd
from ..shared.sensors import inspect_all_sensors


### Sensorendetails anzeigen
@inspect_all_sensors
def show_sensor_details(sensor: pd.DataFrame, *, sensor_name: str) -> None:
    '''TAP FUNKTION: Gibt Details zu jedem Sensor aus.'''
    print(f"{sensor_name:<20} rows={len(sensor):>7}  NaNs={sensor.isna().sum().sum():>7}")
    return None