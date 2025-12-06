from src.untergrund.context import Ctx
from untergrund.shared.inspect import start_end, print_description, print_info, head_tail, row_col_nan_dur_freq
from ..pipeline import CtxPipeline
import pandas as pd
import numpy as np
from scipy.stats import kurtosis as scipy_kurtosis
from typing import Any,cast


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


def compute_optimal_exponent(
    ctx: "Ctx",
    window_key: str,
    feature: str = "acc_rms",
    confidence_threshold: float = 0.7, # hier muss noch ein sinniger default wert empirisch ermittelt werden
    min_r_squared: float = 0.6, # was sind hier sinnvolle werte?
    fallback_exponent: float = 1.5 # sinnvollen exponent empirisch ermitteln (kalibrierungsfahrten?)
    ##### fallback exponenten ggf. per config für alle Funktionen die ihn nutzen global bereitstllen?
) -> float:
    """
    Berechnet optimalen Geschwindigkeits-Exponenten für die Normalisierung.

    Führt log-lineare Regression durch: log(feature) = log(a) + n*log(v)
    → feature = a * v^n, wobei n der gesuchte Exponent ist.

    Args:
        ctx: Context mit Features-DataFrame
        window_key: Schlüssel in ctx.features (z.B. "cluster")
        feature: Referenz-Feature für Kalibrierung (typischerweise "acc_rms")
        confidence_threshold: Minimum v_confidence um Fenster zu inkludieren
        min_r_squared: Minimum R² um Regression zu akzeptieren
        fallback_exponent: Default falls Kalibrierung fehlschlägt

    Returns:
        float: Kalibrierter Exponent (oder fallback)

    Example:
        >>> exponent_amp = compute_optimal_exponent(ctx, "cluster")
        >>> add_f(normalize_features_by_velocity, velocity_exponent=exponent_amp)

    TODO:
        Später soll eine separate Funktion diesen Wert in artifacts speichern. Also ein Funktion am ende der Pipeline die alle relevanten Parameter sammelt und in artifacts ablegt.
    """
    from scipy.stats import linregress

    fdf = ctx.features[window_key]

    # Prüfen ob benötigte Spalten vorhanden sind
    required_cols = {"v", "v_confidence", feature}
    missing = required_cols - set(fdf.columns)
    if missing:
        print(f"[Warning] compute_optimal_exponent: Fehlende Spalten {missing}, using fallback={fallback_exponent}")
        return fallback_exponent

    # Input validierung:
    mask = (
        # confidence über treshold?
        (fdf["v_confidence"] > confidence_threshold) &
        # v görßer Null und nicht NaN?
        (fdf["v"] > 0) &
        (fdf["v"].notna()) &
        # Feature görßer Null und nicht NaN?
        (fdf[feature] > 0) & # ggf. problematisch bei Features die absichtlich auch negative werte haben -> log ist halt bei negativen werten nicht definiert => Fallback???
        (fdf[feature].notna())
    )

    # mindestens x Datenpunkte für robuste Regression -> fallback für kurze testdatensätze
    n_valid = mask.sum()
    if n_valid < 50:  
        print(f"[Warning] compute_optimal_exponent: Nur {n_valid} Fenster für Kalibrierung (< 50), using fallback={fallback_exponent}")
        return fallback_exponent

    # Extrahiere Daten
    v = fdf.loc[mask, "v"].values
    f = fdf.loc[mask, feature].values

    ### Log-linear Regression: log(f) = log(a) + n*log(v)
    # Physikalisch: Feature = "Untergrundwert" * v**n
    # gesucht ist der Exponent n -> durch Logarithmus "Trick" auf lineare Skala bringen (beide seiten logarithmieren)
    # mit klassischer Linearer-Regression Steigung n der Ausgleichsgeraden ermitteln
    # => n entspricht dem potentiell besten exponenten -> validierung durch scoreing!
    try:
        log_v = np.log(v)
        log_f = np.log(f)

        slope, intercept, r_value, p_value, std_err = linregress(log_v, log_f)
        # typechecker wieder "doof", also alles casten (wie so oft...)
        slope = cast(float, slope)
        r_value = cast(float, r_value)

        r_squared = r_value ** 2
        exponent = slope
    except (ValueError, RuntimeError) as e:
        # hier besser raise in production???
        print(f"[Warning] compute_optimal_exponent: Regression failed ({e}), using fallback={fallback_exponent}")
        return fallback_exponent

    ####### Besser ohne fallback? (man hat sich ja für die nutzung der Funktion entschieden) -> aber auf jeden fall immer Info, und dicke warnug bei schlechtem Score
    # Validierung: R² Score
    if r_squared < min_r_squared:
        print(f"[Warning] compute_optimal_exponent: Low R²={r_squared:.2f} (< {min_r_squared}), using fallback={fallback_exponent}")
        return fallback_exponent

    # Validierung: Sanity Check (Exponent muss physikalisch plausibel sein)
    if not (1.0 <= exponent <= 3.0):
        original_exponent = exponent
        exponent = np.clip(exponent, 1.0, 3.0)
        print(f"[Warning] compute_optimal_exponent: Unrealistic exponent={original_exponent:.2f}, clamped to {exponent:.2f}")

    print(f"[Info] compute_optimal_exponent: Calibrated exponent={exponent:.2f} (R²={r_squared:.2f}, n_windows={n_valid})")
    return exponent


### RUNNER
def run_features(ctx: "Ctx") -> "Ctx":
    w_key = select_window_key(ctx, "cluster") # <<-- window_key für die Pipeline-Funktionen setzen
    
    # Richtige Spalten im Window-DataFrame?
    required = {"start_utc", "end_utc"}
    if not required.issubset(ctx.features[w_key].columns):
        raise ValueError(f"Im Window-DataFrame '{w_key}' müssen {required} Spalten vorhanden sein.")

    # erster Teil
    pipeline_1 = CtxPipeline()

    def add_f1(fn, **kwargs):
        """Phase 1: Add raw feature functions"""
        pipeline_1.add(fn, source=["sensors","features"], dest="features", fn_kwargs={"window_key": w_key, **kwargs})

    # 1: Geschwindigkeit aus dem Location Sensor holen und confidence berechnen
    add_f1(compute_window_velocity)

    # 2: Raw Features
    add_f1(acc_rms)
    add_f1(acc_std)
    add_f1(acc_p2p)
    add_f1(zero_crossing_rate)
    add_f1(acc_kurtosis)

    # Pipeline erstmal ausführen, da ich zur Ermittung des Exponenten die Raw Features brauche
    ctx = pipeline_1(ctx)

    # Exonenten ermitteln
    exponent_amp = compute_optimal_exponent(ctx, w_key, feature="acc_rms")
    # Optional: exponent_freq = compute_optimal_exponent(ctx, w_key, feature="zero_crossing_rate") <- sollte nahe "1" sein

    # rest in zweiter pipeline
    pipeline_2 = CtxPipeline()

    def add_f2(fn, **kwargs):
        """Phase 2: Add normalization functions"""
        pipeline_2.add(fn, source=["sensors","features"], dest="features", fn_kwargs={"window_key": w_key, **kwargs})

    # 3: Features v-normalisieren
    add_f2(
        normalize_features_by_velocity,  # Amplituden-Features
        cfg=ctx.config,
        feature_columns=["acc_rms", "acc_std", "acc_p2p"],
        velocity_exponent=exponent_amp  # hier der ermittelte Exponent
    )
    add_f2(
        normalize_features_by_velocity,  
        cfg=ctx.config,
        feature_columns=["zero_crossing_rate"],
        velocity_exponent=1.0  
    )

    # Inspektoren
    pipeline_2.tap(row_col_nan_dur_freq, source="features")
    pipeline_2.tap(head_tail, source="features")
    pipeline_2.tap(print_info, source="features")
    pipeline_2.tap(print_description, source="features")
    pipeline_2.tap(start_end, source="features")

    print("\nFeature-Pipeline Phase 2 Repr:")
    print(pipeline_2)
    return pipeline_2(ctx)


### Features: 

def compute_window_velocity(
    sensors: dict[str, pd.DataFrame],
    features: dict[str, pd.DataFrame],
    *,
    window_key: str,
    sensor_name: str = "Location",
    cols: list[str] = ["speed", "speedAccuracy"],
    min_speed: float = 0.3,
    max_speed: float = 20.0,
    aggregation: str = "median",
    speedacc_scale: float = 5.0,
    penalty_1_point: float = -0.15,
    penalty_2_points: float = -0.05
) -> dict[str, pd.DataFrame]:
    """
    Extrahiert Geschwindigkeit aus GPS-Location-Sensor und berechnet einen Confidence-Score.

    Fügt 2 Spalten zu features[window_key] hinzu:
    - v: Aggregierte Geschwindigkeit (m/s) über das Fenster
    - v_confidence: Validierungswert (0.0-1.0) basierend auf 3 Faktoren

    Confidence-Faktoren:
    1. Speed-Range -> Showstopper (min_speed bis max_speed)
    2. speedAccuracy (Hauptfaktor, ~80% Gewicht)
    3. GPS-Punktanzahl (Anzahl der GPS-Punkte im Fenster)
    4. Stabilität (noch nicht implementiert)

    Args:
        sensors: Sensor-Dictionary mit Location-Sensor
        features: Features-Dictionary mit Window-DataFrame
        window_key: Schlüssel für Window-DataFrame
        sensor_name: Name des GPS-Sensors (default: "Location")
        cols: Spalten-Namen [speed_col, speedAccuracy_col]
        min_speed: Minimum plausible speed in m/s (Showstopper)
        max_speed: Maximum plausible speed in m/s (Showstopper)
        aggregation: Aggregationsmethode ("median" | "mean")
        speedacc_scale: Skalierungsfaktor für speedAccuracy → confidence
        penalty_1_point: Confidence-Penalty für einzelnen GPS-Punkt
        penalty_2_points: Confidence-Penalty für zwei GPS-Punkte

    Returns:
        Features-Dictionary mit aktualisierten Spalten v und v_confidence

    Raises:
        ValueError: Wenn sensor_name nicht existiert oder cols fehlen
        ValueError: Wenn aggregation nicht "median" oder "mean" ist
    """
    if sensor_name not in sensors:
        raise ValueError(f"Sensor '{sensor_name}' not found in sensors dict.")

    fdf = features[window_key].copy()
    location = sensors[sensor_name]

    # Prüfe ob Location-Sensor benötigte Spalten hat
    missing_cols = [c for c in cols if c not in location.columns]
    if missing_cols:
        raise ValueError(f"[compute_window_velocity] Im Sensor '{sensor_name}' fehlen Spalten: {missing_cols}")

    # Validiere aggregation Parameter
    if aggregation not in ["median", "mean"]:
        raise ValueError(f"[compute_window_velocity] aggregation must be 'median' or 'mean', got '{aggregation}'")

    # Spalten extrahieren
    speed_col = cols[0]
    speedacc_col = cols[1]

    v_values = []
    v_confidence_values = []
    nan_count = 0

    for i, row in fdf.iterrows():
        start_utc = row["start_utc"]
        end_utc = row["end_utc"]

        # GPS-Punkte im Fenster filtern
        window_data = location.loc[(location.index >= start_utc) & (location.index < end_utc), cols]

        # Nur valide GPS-Punkte nutzen (negative Werte = ungültig laut Sensor Logger Doku)
        valid_mask = (window_data[speed_col] >= 0) & (window_data[speedacc_col] >= 0)
        valid_speeds = window_data.loc[valid_mask, speed_col]
        valid_accs = window_data.loc[valid_mask, speedacc_col]

        # Keine validen GPS-Punkte im Fenster
        if len(valid_speeds) == 0:
            v_values.append(np.nan)
            v_confidence_values.append(np.nan)
            nan_count += 1
            continue

        # Geschwindigkeit: Aggregation über valide Punkte
        if aggregation == "median":
            v = valid_speeds.median()
        else:  # aggregation == "mean"
            v = valid_speeds.mean()

        # Confidence berechnen (4 Faktoren)

        # Faktor 1: Min/Max Speed -> Showstopper, physikalisch unrealistische Werte führen zu einer sofortigen confidence von 0
        if v < min_speed or v > max_speed:
            v_confidence = 0.0
            v_values.append(v)
            v_confidence_values.append(v_confidence)
            continue

        # Faktor 2: speedAccuracy (Hauptfaktor, ~80% Gewicht)
        # -> Hypothese: Sensor kennt seine eigene Unsicherheit am besten
        mean_speedAcc = valid_accs.mean() # oder besser auch/zusätzlich median???
        confidence_base = max(1.0 - mean_speedAcc / speedacc_scale, 0.0)

        # Faktor 3: GPS-Punktanzahl (Robustheit)
        # Einzelmessung unsicher -> je mehr GPS Punkte in einem Fenster um so genauer!
        n_points = len(valid_speeds)
        if n_points == 1:
            penalty_points = penalty_1_point
        elif n_points == 2:
            penalty_points = penalty_2_points
        else:
            penalty_points = 0.0

        # Faktor 4: Stabilität (Platzhalter)
        # TODO nach MVP: Variation der Werte innerhalt eines Fensters (und ggf. Nachbarfenster)
        # -> Problem: Bei Beschleunigung/Bremsen auch hohe Variation → false positives
        penalty_stability = 0.0

        # Aggregation
        v_confidence = max(
            confidence_base + penalty_points + penalty_stability,
            0.0
        )

        v_values.append(v)
        v_confidence_values.append(v_confidence)

    if nan_count > 0:
        print(f"[Warning] compute_window_velocity: {nan_count} windows had no valid GPS data.")

    fdf["v"] = v_values
    fdf["v_confidence"] = v_confidence_values
    return {**features, window_key: fdf}


def acc_rms(sensors: dict[str, pd.DataFrame], features: dict[str, pd.DataFrame], *, window_key: str, sensor_name: str = "Accelerometer", cols: list[str] = ["x", "y", "z"]) -> dict[str, pd.DataFrame]:
    """
    Berechnet die Magnitude-RMS der Beschleunigung über alle Achsen pro Fenster.
    - Maß für die mittlere Vibrationsstärke
    --> Wie Intensiv ist die Vibration?
    WICHTIG: Stark geschwindigkeitsabhängig
    - Im idealisierten Modell wächst die Amplitude mit v**n mit n=2
    - der reale Exponent wird später empirisch ermittelt. (Erwartung: n = 1,2 bis 1,8)
    """
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

def acc_std(sensors: dict[str, pd.DataFrame], features: dict[str, pd.DataFrame], *, window_key: str, sensor_name: str = "Accelerometer", cols: list[str] = ["x", "y", "z"]) -> dict[str, pd.DataFrame]:
    """
    Standardabweichung der Magnitude (Beschleunigungssenor) über alle Achsen pro Fenster
    - misst die Variabilität der Vibrationsstärke über die Zeit.
    WICHTIG: Stark geschwindigkeitsabhängig
    - Im idealisierten Modell wächst die Amplitude mit v**n mit n=2
    - der reale Exponent wird später empirisch ermittelt. (Erwartung: n = 1,2 bis 1,8)
    """
    if sensor_name not in sensors:
        raise ValueError(f"Sensor '{sensor_name}' not found in sensors dict.")

    fdf = features[window_key].copy()
    acc = sensors[sensor_name]

    missing_cols = [c for c in cols if c not in acc.columns]
    if missing_cols:
        raise ValueError(f"[acc_std] Im Sensor '{sensor_name}' fehlen Spalten: {missing_cols}")

    std_values = []
    nan_count = 0
    for i, row in fdf.iterrows(): #ggf. später ohne das "kostbare" iterrows() implementieren
        start_utc = row["start_utc"]
        end_utc = row["end_utc"]
        window_data = acc.loc[(acc.index >= start_utc) & (acc.index < end_utc), cols]
        if len(window_data) == 0:
            std_values.append(np.nan)
            nan_count += 1
            continue

        # Magnitude berechnen: sqrt(x² + y² + z²) pro Zeitpunkt
        magnitude = np.sqrt((window_data[cols]**2).sum(axis=1))

        # Standardabweichung der Magnitude-Zeitreihe
        std = np.std(magnitude)
        std_values.append(std)

    if nan_count > 0:
        print(f"[Warning] acc_std: {nan_count} windows had no data and resulted in NaN STD values.")

    fdf["acc_std"] = std_values
    return {**features, window_key: fdf}


def acc_p2p(sensors: dict[str, pd.DataFrame], features: dict[str, pd.DataFrame], *, window_key: str, sensor_name: str = "Accelerometer", cols: list[str] = ["x", "y", "z"]) -> dict[str, pd.DataFrame]:
    """
    Größten Peak im Fenster über alle Achsen berechnen (Maximum - Minimum).
    - Gut für Anomalie erkennung und Debugging, weniger für das Clustering
    WICHTIG: Stark geschwindigkeitsabhängig
    - Im idealisierten Modell wächst die Amplitude mit v**n mit n=2
    - der reale Exponent wird später empirisch ermittelt. (Erwartung: n = 1,2 bis 1,8)
    """
    ### TODO Was ist bei diagonalem Vektor?
    if sensor_name not in sensors:
        raise ValueError(f"Sensor '{sensor_name}' not found in sensors dict.")

    fdf = features[window_key].copy()
    acc = sensors[sensor_name]

    missing_cols = [c for c in cols if c not in acc.columns]
    if missing_cols:
        raise ValueError(f"[acc_p2p] Im Sensor '{sensor_name}' fehlen Spalten: {missing_cols}")

    p2p_values = []
    nan_count = 0
    for i, row in fdf.iterrows(): #ggf. später ohne das "kostbare" iterrows() implementieren
        start_utc = row["start_utc"]
        end_utc = row["end_utc"]
        window_data = acc.loc[(acc.index >= start_utc) & (acc.index < end_utc), cols]
        if len(window_data) == 0:
            p2p_values.append(np.nan)
            nan_count += 1
            continue

        # Peak-to-Peak: Maximum - Minimum über alle Achsen
        max_val = window_data.max().max()  # Größter Wert in allen Spalten
        min_val = window_data.min().min()  # Kleinster Wert in allen Spalten
        p2p = max_val - min_val

        p2p_values.append(p2p)

    if nan_count > 0:
        print(f"[Warning] acc_p2p: {nan_count} windows had no data and resulted in NaN P2P values.")

    fdf["acc_p2p"] = p2p_values
    return {**features, window_key: fdf}


def zero_crossing_rate(sensors: dict[str, pd.DataFrame], features: dict[str, pd.DataFrame], *, window_key: str, sensor_name: str = "Accelerometer", cols: list[str] = ["x", "y", "z"]) -> dict[str, pd.DataFrame]:
    """
    Zero-Crossing-Rate (ZCR) berechnen: mittlere Vorzeichenwechsel-Rate über alle Achsen.
    -> Freqenz der Vibration

    WICHTIG: annähernd linear geschwindigkeitsabhängig (v**n mit n=1)
    - auch hier kann der reale Wert leicht abweichen. (Erwartung: n = 1)
    """
    if sensor_name not in sensors:
        raise ValueError(f"Sensor '{sensor_name}' not found in sensors dict.")

    fdf = features[window_key].copy()
    acc = sensors[sensor_name]

    missing_cols = [c for c in cols if c not in acc.columns]
    if missing_cols:
        raise ValueError(f"[zero_crossing_rate] Im Sensor '{sensor_name}' fehlen Spalten: {missing_cols}")

    zcr_values = []
    nan_count = 0
    for i, row in fdf.iterrows():
        start_utc = row["start_utc"]
        end_utc = row["end_utc"]
        window_data = acc.loc[(acc.index >= start_utc) & (acc.index < end_utc), cols]
        if len(window_data) == 0:
            zcr_values.append(np.nan)
            nan_count += 1
            continue

        # ZCR pro Achse berechnen (nicht über alle Achsen gemischt!)
        zcr_per_axis = []
        for col in cols:
            signal = np.asarray(window_data[col].values)  # Explizit zu numpy array
            # Vorzeichenwechsel zählen
            sign_changes = np.sum(np.diff(np.sign(signal)) != 0)
            zcr = sign_changes / len(signal)  # RATE: normalisiert auf Sample-Anzahl
            zcr_per_axis.append(zcr)

        # Durchschnitt über alle Achsen → durchschnittliche Frequenz-Charakteristik
        zcr_mean = np.mean(zcr_per_axis)
        zcr_values.append(zcr_mean)

    if nan_count > 0:
        print(f"[Warning] zero_crossing_rate: {nan_count} windows had no data and resulted in NaN ZCR values.")

    fdf["zero_crossing_rate"] = zcr_values
    return {**features, window_key: fdf}


def acc_kurtosis(sensors: dict[str, pd.DataFrame], features: dict[str, pd.DataFrame], *, window_key: str, sensor_name: str = "Accelerometer", cols: list[str] = ["x", "y", "z"]) -> dict[str, pd.DataFrame]:
    """
    Excess-Kurtosis (Kurtosis - 3) der Magnitude über alle Achsen pro Fenster berechnen.
    - Misst die Häufigkeit von Extremwerten in der Vibrationsstärke:
    Interpretation (Normal ≈ 0), erwartete Werte:
    - < 0: Flache Verteilung, gleichmäßig (z.B. glatter Aspahlt)
    - ≈ 0: Normalverteilung (typische Straße)
    - 0-3: Leicht erhöht, gelegentliche Peaks (z.B. Kopfstein)
    - 3-10: Stark erhöht, häufige Extremwerte (z.B. Schlaglöcher)
    - > 10: Sehr stark (viele krasse Stöße, z.B. MTB)
    --> Später empirisch Prüfen!

    WICHTIG: weitestgehend Geschwindigkeitsunabhängig (v-unabhängig durch σ-Normierung!)
    - in der realität warscheinlich auch leicht v-Abhängig, ich hoffe aber nicht maßgeblich.
    --> kann daher als direkter Feeature genutzt werden
    """
    if sensor_name not in sensors:
        raise ValueError(f"Sensor '{sensor_name}' not found in sensors dict.")

    fdf = features[window_key].copy()
    acc = sensors[sensor_name]

    missing_cols = [c for c in cols if c not in acc.columns]
    if missing_cols:
        raise ValueError(f"[acc_kurtosis] Im Sensor '{sensor_name}' fehlen Spalten: {missing_cols}")

    kurt_values = []
    nan_count = 0
    for i, row in fdf.iterrows():
        start_utc = row["start_utc"]
        end_utc = row["end_utc"]
        window_data = acc.loc[(acc.index >= start_utc) & (acc.index < end_utc), cols]
        if len(window_data) == 0:
            kurt_values.append(np.nan)
            nan_count += 1
            continue

        # Magnitude berechnen: sqrt(x² + y² + z²) pro Zeitpunkt
        magnitude = np.sqrt((window_data[cols]**2).sum(axis=1))

        # Kurtosis der Magnitude-Zeitreihe (Excess: fisher=True)
        kurt = scipy_kurtosis(magnitude, fisher=True, nan_policy='propagate')

        kurt_values.append(kurt)

    if nan_count > 0:
        print(f"[Warning] acc_kurtosis: {nan_count} windows had no data and resulted in NaN Kurtosis values.")

    fdf["acc_kurtosis"] = kurt_values
    return {**features, window_key: fdf}


def normalize_features_by_velocity(
    sensors: dict[str, pd.DataFrame],
    features: dict[str, pd.DataFrame],
    *,
    window_key: str,
    cfg: dict[str, Any] | None = None,
    velocity_exponent: float = 1.5,
    velocity_epsilon: float = 0.1,
    v_confidence_threshold: float = 0.5,
    confidence_strategy: str = "hard_threshold",
    feature_columns: list[str] | None = None
) -> dict[str, pd.DataFrame]:
    """
    Normalisiert geschwindigkeitsabhängige Features durch GPS-Geschwindigkeit.

    Erstellt neue Spalten mit Suffix '_vnorm':
        feature_vnorm = feature_raw / (v^velocity_exponent + velocity_epsilon)

    Args:
        sensors: Sensor-Dictionary (nicht verwendet, Signatur-Konsistenz)
        features: Features-Dictionary mit v, v_confidence Spalten
        window_key: Schlüssel für Window-DataFrame
        cfg: Config-Dictionary (optional, überschreibt Defaults)
        velocity_exponent: Potenz-Exponent (default: 1.5 für Amplitude-Features)
        velocity_epsilon: Epsilon gegen Division durch 0 (default: 0.1 m/s)
        v_confidence_threshold: Minimum Confidence für Normalisierung (default: 0.5)
        confidence_strategy: "hard_threshold" | "soft_fallback" | "weighted"
        feature_columns: Liste von Features zum Normalisieren (default: None = Auto-Detect)

    Returns:
        Features-Dict mit neuen *_vnorm Spalten

    Raises:
        ValueError: Fehlender window_key, fehlende v/v_confidence Spalten
        ValueError: Ungültige Parameter (exponent <= 0, etc.)
        NotImplementedError: Placeholder-Strategien
    """
    # Config-Parameter laden (Fallback zu Function-Defaults)
    if cfg and "velocity_normalization" in cfg:
        vnorm_cfg = cfg["velocity_normalization"]
        velocity_epsilon = vnorm_cfg.get("velocity_epsilon", velocity_epsilon)
        v_confidence_threshold = vnorm_cfg.get("v_confidence_threshold", v_confidence_threshold)
        confidence_strategy = vnorm_cfg.get("confidence_strategy", confidence_strategy)
        # velocity_exponent wird NICHT aus Config gelesen (Pipeline-Parameter!)
        # feature_columns wird NICHT aus Config gelesen (Pipeline-Parameter!)
    else:
        print("[Info] normalize_features_by_velocity: No 'velocity_normalization' config found, using default parameters.")

    fdf = features[window_key].copy()

    # Required v-columns vorhanden? (compute_window_velocity() zuerst ausführen!)
    required = ["v", "v_confidence"]
    missing = [c for c in required if c not in fdf.columns]
    if missing:
        raise ValueError(
            f"[normalize_features_by_velocity] Missing required v-columns in features['{window_key}']: {missing}. "
            "Ensure compute_window_velocity runs before this function!!!"
        )

    # Parameter-Validierung
    if velocity_exponent <= 0:
        raise ValueError(f"[normalize_features_by_velocity] velocity_exponent must be > 0, got {velocity_exponent}")

    if velocity_epsilon < 0:
        raise ValueError(f"[normalize_features_by_velocity] velocity_epsilon must be >= 0, got {velocity_epsilon}")

    if not 0 <= v_confidence_threshold <= 1:
        raise ValueError(
            f"[normalize_features_by_velocity] v_confidence_threshold must be in [0, 1], got {v_confidence_threshold}"
        )

    # Strategie-Validierung
    allowed_strategies = ["hard_threshold", "soft_fallback", "weighted"]
    if confidence_strategy not in allowed_strategies:
        raise ValueError(
            f"[normalize_features_by_velocity] Unknown confidence_strategy: '{confidence_strategy}'. "
            f"Allowed: {allowed_strategies}"
        )
    
    # TODO: Alternativer Umgang mit schlechter v_confidence???
    # Placeholder-Strategien
    if confidence_strategy in ["soft_fallback", "weighted"]:
        raise NotImplementedError(
            f"[normalize_features_by_velocity] confidence_strategy='{confidence_strategy}' is a placeholder for Phase 4. "
            "Currently only 'hard_threshold' is implemented."
        )

    # Falls keine Features ausgewählt wurden, keine Normalisierung -> vorzeitiger Return der oroginalen Features
    if feature_columns is None:
        print(
            f"[Info] normalize_features_by_velocity: No feature-columns-list provided -> skipping normalization for window_key='{window_key}'"
        )
        return features
    
    # Prüfen, ob alle feature_columns im Feature_DF vorhanden sind
    missing_cols = [c for c in feature_columns if c not in fdf.columns]
    if missing_cols:
        print(f"[Warning] normalize_features_by_velocity: The following feature_columns were not found in the DataFrame and will be skipped: {missing_cols}")
        # feature_columns neu setzen mit nur vorhandenen Features!
        feature_columns = [c for c in feature_columns if c in fdf.columns]
        print(f"[Info] normalize_features_by_velocity: Updated feature_columns: {feature_columns}. (If empty -> skipping normalization)")
        # keine Feature-columns -> vorzeitiger Return!
        if not feature_columns:
            print(f"[Info] skipped!")
            return features


    # Normalisierungsfaktor berechnen
    v_norm_factor = fdf["v"] ** velocity_exponent + velocity_epsilon

    # Confidence-Strategie anwenden (nur hard_threshold implementiert)
    if confidence_strategy == "hard_threshold":
        low_confidence_mask = fdf["v_confidence"] < v_confidence_threshold
        v_norm_factor[low_confidence_mask] = np.nan

    # Features normalisieren
    for feat in feature_columns:
        fdf[f"{feat}_vnorm"] = fdf[feat] / v_norm_factor

    # Warnings
    low_conf_count = (fdf["v_confidence"] < v_confidence_threshold).sum()
    if low_conf_count > 0:
        print(
            f"[Warning] normalize_features_by_velocity: {low_conf_count}/{len(fdf)} windows "
            f"have confidence < {v_confidence_threshold}. Setting vnorm=NaN for these."
        )

    nan_v_count = fdf["v"].isna().sum()
    if nan_v_count > 0:
        print(
            f"[Warning] normalize_features_by_velocity: {nan_v_count}/{len(fdf)} windows "
            f"have NaN velocity. vnorm will also be NaN."
        )

    return {**features, window_key: fdf}

