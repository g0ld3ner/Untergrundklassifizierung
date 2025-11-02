
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

### KI zeugs zum überarbeiten:
# Zeitzonen-Inspektion
@inspect_all_sensors
def tz_inspect(
    sensor: pd.DataFrame,
    *,
    sensor_name: str,
    require_utc: bool = True,
    fail_on_violation: bool = False,
) -> None:
    """
    Prüft Zeitzonen-Konsistenz:
      - Index tz-aware/naiv? Wenn aware: UTC?
      - Datetime-Spalten tz-aware/naiv? Wenn aware: UTC?
      - Erkannt wird jede Mischung (aware + naiv) sowie Non-UTC bei require_utc=True.
    Keine Mutation des DataFrames.
    """

    def tz_of_index(idx: pd.Index) -> Optional[str]:
        tz = getattr(idx, "tz", None)
        if tz is None:
            return None
        z = getattr(tz, "zone", None)
        return z if z is not None else str(tz)

    def tz_of_series(s: pd.Series) -> Optional[str]:
        if not pd.api.types.is_datetime64_any_dtype(s):
            return None
        tz = getattr(getattr(s, "dt", None), "tz", None)
        if tz is None:
            return None
        z = getattr(tz, "zone", None)
        return z if z is not None else str(tz)

    lines = []
    issues = []

    # Index
    idx_tz = tz_of_index(sensor.index)
    lines.append(f"[Index] {type(sensor.index).__name__}, tz={idx_tz or 'naive'}")

    # Datetime-Spalten
    dt_cols = [c for c in sensor.columns if pd.api.types.is_datetime64_any_dtype(sensor[c])]
    if dt_cols:
        lines.append("[Columns] datetime64-Spalten:")
        for c in dt_cols:
            tz = tz_of_series(sensor[c])
            lines.append(f"  - {c}: tz={tz or 'naive'}")
    else:
        lines.append("[Columns] keine datetime64-Spalten")

    # Bewertung: Index immer mitprüfen (auch wenn naiv)
    aware_flags = [("__index__", idx_tz)]
    for c in dt_cols:
        aware_flags.append((c, tz_of_series(sensor[c])))

    any_aware = any(tz is not None for _, tz in aware_flags)
    any_naive = any(tz is None for _, tz in aware_flags)

    # Mischung aware/naiv?
    if any_aware and any_naive:
        issues.append("Mix aus tz-aware und tz-naiv (Index/Spalten uneinheitlich)")

    # Policy: wenn require_utc=True → alles Aware muss UTC sein
    if require_utc:
        non_utc = [name for name, tz in aware_flags if tz is not None and tz.upper() != "UTC"]
        if non_utc:
            issues.append(f"tz-aware ≠ UTC in: {', '.join(non_utc)}")
        # Optional: Index soll ebenfalls UTC-aware sein (keine naive Zeitachse)
        if idx_tz is None and any_aware:
            issues.append("Index ist tz-naiv, aber es existieren tz-aware Spalten (Index sollte UTC-aware sein)")
        if idx_tz is None and not any_aware:
            # Alles naiv → je nach Policy als Hinweis/Issue behandeln
            issues.append("Alle Zeitachsen sind tz-naiv; erwartet: UTC-aware (Index und Spalten)")

    # Ausgabe
    print(f"===== TZ-Inspect: {sensor_name} =====")
    for ln in lines:
        print(ln)
    if issues:
        print("[Status] 🚨 Probleme erkannt:")
        for it in issues:
            print(f"  - {it}")
    else:
        status = "UTC-aware konsistent" if any_aware and not any_naive else "einheitlich tz-naiv"
        print(f"[Status] ✅ {status}")
    print("-" * (len(sensor_name) + 30))

    if fail_on_violation and issues:
        raise ValueError(f"TZ-Policy verletzt ({sensor_name}): " + " | ".join(issues))

    return None

# D-Tale: https://github.com/sdorra/d-tale
@inspect_all_sensors
def dtale_inspect(
    sensor: pd.DataFrame,
    *,
    sensor_name: str,
    open_browser: bool = False,
) -> None:
    """Öffnet D-Tale für den Sensor. Für die Anzeige werden tz-aware Datetimes tz-naiv gemacht (Kopie!)."""
    try:
        import dtale
    except Exception:
        print("[D-Tale] Paket nicht installiert. pip install dtale")
        return

    # 1) Session-Name sanitisieren (D-Tale verbietet Sonderzeichen)
    import re
    session_name = re.sub(r"[^A-Za-z0-9 ]+", "", f"sensor_{sensor_name}")

    # 2) Ansicht für D-Tale vorbereiten: tz-aware -> tz-naiv (nur Kopie)
    view = sensor.copy()

    # Index (nur falls DatetimeIndex mit TZ)
    if isinstance(view.index, pd.DatetimeIndex) and view.index.tz is not None:
        # nach UTC konvertieren und TZ entfernen -> datetime64[ns] (naiv)
        view.index = view.index.tz_convert("UTC").tz_localize(None)

    # Spalten: alle datetime64* finden und ggf. naiv machen
    dt_cols = [c for c in view.columns if pd.api.types.is_datetime64_any_dtype(view[c])]
    for c in dt_cols:
        s = view[c]
        tz = getattr(getattr(s, "dt", None), "tz", None)
        if tz is not None:
            view[c] = s.dt.tz_convert("UTC").dt.tz_localize(None)

    # 3) D-Tale starten
    sess = dtale.show(view, name=session_name, open_browser=False, host="127.0.0.1", theme="dark" ,subprocess=False, reaper_on=True)
    url_attr = getattr(sess, "_main_url", None)
    url = url_attr() if callable(url_attr) else (str(url_attr) if url_attr else "unknown")

    print(f"===== Sensor: {sensor_name} (D-Tale) =====")
    print(f"Session: {session_name}")
    print(f"URL: {url}")
    print("-" * (len(sensor_name) + 30))

    if open_browser:
        try:
            sess.open_browser()
        except Exception:
            print("[D-Tale] Browser konnte nicht automatisch geöffnet werden. URL manuell öffnen.")
    return None