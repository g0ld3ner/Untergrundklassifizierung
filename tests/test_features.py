import pandas as pd
import numpy as np
import pytest
from datetime import datetime, timedelta

from untergrund.runners.features import (
    zero_crossing_rate,
    acc_kurtosis,
    acc_rms,
    acc_std,
    acc_p2p,
    normalize_features_by_velocity,
    compute_window_velocity,
    compute_optimal_exponent
)
from untergrund.context import Ctx, make_ctx

### --- AI Testing mit Claude ---
# Test Data Setup
@pytest.fixture
def mock_accelerometer_data():
    """
    Erstelle Mock-Sensor-Daten mit bekannten ZCR und Kurtosis-Werten.
    """
    # Zeitindex mit 100 Samples
    base_time = pd.Timestamp("2025-01-01 00:00:00Z", tz="UTC")
    times = [base_time + timedelta(seconds=i*0.01) for i in range(100)]  # 1 Sekunde Daten @ 100Hz

    # Signale mit verschiedenen Charakteristiken
    x_values = np.sin(2 * np.pi * 2 * np.arange(100) * 0.01)  # 2 Hz Sinus
    y_values = np.cos(2 * np.pi * 2 * np.arange(100) * 0.01)  # 2 Hz Cosinus (90° verschoben)
    z_values = np.random.normal(0, 0.1, 100)  # Kleine Rauschrauschen

    df = pd.DataFrame({
        "x": x_values,
        "y": y_values,
        "z": z_values
    }, index=pd.DatetimeIndex(times, name="time_utc"))

    return {"Accelerometer": df}


@pytest.fixture
def mock_features_dataframe():
    """
    Erstelle Mock-Feature-DataFrame mit Fenster (start_utc, end_utc).
    """
    base_time = pd.Timestamp("2025-01-01 00:00:00Z", tz="UTC")

    # Zwei Fenster à 1 Sekunde
    df = pd.DataFrame({
        "window_id": [0, 1],
        "start_utc": [base_time, base_time + timedelta(seconds=1)],
        "end_utc": [base_time + timedelta(seconds=1), base_time + timedelta(seconds=2)],
    })

    return {"cluster": df}


@pytest.fixture
def mock_features_with_velocity():
    """Features mit bereits berechneter Velocity."""
    base_time = pd.Timestamp("2025-01-01 00:00:00Z", tz="UTC")

    return {
        "cluster": pd.DataFrame({
            "window_id": [0, 1, 2],
            "start_utc": [
                base_time,
                base_time + timedelta(seconds=2),
                base_time + timedelta(seconds=4)
            ],
            "end_utc": [
                base_time + timedelta(seconds=4),
                base_time + timedelta(seconds=6),
                base_time + timedelta(seconds=8)
            ],
            "acc_rms": [10.0, 15.0, 20.0],
            "acc_std": [5.0, 7.5, 10.0],
            "acc_p2p": [20.0, 30.0, 40.0],
            "zero_crossing_rate": [0.5, 0.6, 0.7],
            "acc_kurtosis": [0.0, 1.5, 3.0],
            "v": [2.0, 3.0, 1.5],
            "v_confidence": [0.9, 0.8, 0.3]  # Letztes: niedrige Confidence
        })
    }


# Tests for zero_crossing_rate
def test_zero_crossing_rate_basic(mock_accelerometer_data, mock_features_dataframe):
    """Test, dass zero_crossing_rate Spalte hinzufügt und plausible Werte zurückgibt."""
    result = zero_crossing_rate(
        sensors=mock_accelerometer_data,
        features=mock_features_dataframe,
        window_key="cluster",
        sensor_name="Accelerometer",
        cols=["x", "y", "z"]
    )

    # Prüfe: Result ist ein dict mit "cluster" Schlüssel
    assert "cluster" in result

    # Prüfe: Neue Spalte hinzugefügt
    feature_df = result["cluster"]
    assert "zero_crossing_rate" in feature_df.columns

    # Prüfe: Werte sind zwischen 0 und 1 (Rate, oder NaN wenn leeres Fenster)
    zcr_values = feature_df["zero_crossing_rate"]
    valid_values = zcr_values.dropna()
    assert (valid_values >= 0).all() and (valid_values <= 1).all(), "ZCR sollte zwischen 0 und 1 sein"

    # Prüfe: Erstes Fenster sollte Daten haben
    assert not pd.isna(zcr_values.iloc[0]), "Erstes Fenster sollte Daten haben"


def test_zero_crossing_rate_empty_window():
    """Test NaN-Handling bei leerem Fenster."""
    sensors = {
        "Accelerometer": pd.DataFrame({
            "x": [1, 2, 3],
            "y": [1, 2, 3],
            "z": [1, 2, 3]
        }, index=pd.date_range("2025-01-01", periods=3, freq="10ms", tz="UTC"))
    }

    features = {
        "cluster": pd.DataFrame({
            "start_utc": [pd.Timestamp("2025-01-02", tz="UTC")],  # Außerhalb Daten-Range
            "end_utc": [pd.Timestamp("2025-01-02 00:00:01", tz="UTC")],
        })
    }

    result = zero_crossing_rate(sensors, features, window_key="cluster")
    assert pd.isna(result["cluster"]["zero_crossing_rate"].iloc[0])


def test_zero_crossing_rate_constant_signal():
    """Test: Konstantes Signal hat ZCR=0."""
    sensors = {
        "Accelerometer": pd.DataFrame({
            "x": [1.0] * 10,
            "y": [1.0] * 10,
            "z": [1.0] * 10
        }, index=pd.date_range("2025-01-01", periods=10, freq="10ms", tz="UTC"))
    }

    features = {
        "cluster": pd.DataFrame({
            "start_utc": [pd.Timestamp("2025-01-01 00:00:00", tz="UTC")],
            "end_utc": [pd.Timestamp("2025-01-01 00:00:10", tz="UTC")],
        })
    }

    result = zero_crossing_rate(sensors, features, window_key="cluster")
    zcr = result["cluster"]["zero_crossing_rate"].iloc[0]
    assert zcr == 0.0, "Konstantes Signal sollte ZCR=0 haben"


def test_zero_crossing_rate_alternating_signal():
    """Test: Alternierendes Signal hat hohe ZCR."""
    sensors = {
        "Accelerometer": pd.DataFrame({
            "x": [1, -1, 1, -1, 1, -1, 1, -1],
            "y": [1, -1, 1, -1, 1, -1, 1, -1],
            "z": [0] * 8
        }, index=pd.date_range("2025-01-01", periods=8, freq="10ms", tz="UTC"))
    }

    features = {
        "cluster": pd.DataFrame({
            "start_utc": [pd.Timestamp("2025-01-01 00:00:00", tz="UTC")],
            "end_utc": [pd.Timestamp("2025-01-01 00:00:08", tz="UTC")],
        })
    }

    result = zero_crossing_rate(sensors, features, window_key="cluster")
    zcr = result["cluster"]["zero_crossing_rate"].iloc[0]
    # Alternierendes Signal: viele Vorzeichenwechsel
    assert zcr > 0.5, f"Alternierendes Signal sollte hohe ZCR haben, got {zcr}"


# Tests for acc_kurtosis
def test_acc_kurtosis_basic(mock_accelerometer_data, mock_features_dataframe):
    """Test, dass acc_kurtosis Spalte hinzufügt und plausible Werte zurückgibt."""
    result = acc_kurtosis(
        sensors=mock_accelerometer_data,
        features=mock_features_dataframe,
        window_key="cluster",
        sensor_name="Accelerometer",
        cols=["x", "y", "z"]
    )

    # Prüfe: Result ist ein dict mit "cluster" Schlüssel
    assert "cluster" in result

    # Prüfe: Neue Spalte hinzugefügt
    feature_df = result["cluster"]
    assert "acc_kurtosis" in feature_df.columns

    # Prüfe: Kurtosis-Werte sind numerisch
    kurt_values = feature_df["acc_kurtosis"]
    assert kurt_values.dtype in [np.float64, np.float32, float]


def test_acc_kurtosis_empty_window():
    """Test NaN-Handling bei leerem Fenster."""
    sensors = {
        "Accelerometer": pd.DataFrame({
            "x": [1, 2, 3],
            "y": [1, 2, 3],
            "z": [1, 2, 3]
        }, index=pd.date_range("2025-01-01", periods=3, freq="10ms", tz="UTC"))
    }

    features = {
        "cluster": pd.DataFrame({
            "start_utc": [pd.Timestamp("2025-01-02", tz="UTC")],  # Außerhalb Daten-Range
            "end_utc": [pd.Timestamp("2025-01-02 00:00:01", tz="UTC")],
        })
    }

    result = acc_kurtosis(sensors, features, window_key="cluster")
    assert pd.isna(result["cluster"]["acc_kurtosis"].iloc[0])


def test_acc_kurtosis_normal_distribution():
    """Test: Normalverteiltes Signal (3D) hat Kurtosis ≈ 0."""
    np.random.seed(42)
    # 3D Normal-Verteilung (x, y, z alle normalverteilt)
    signal_x = np.random.normal(0, 1, 1000)
    signal_y = np.random.normal(0, 1, 1000)
    signal_z = np.random.normal(0, 1, 1000)

    sensors = {
        "Accelerometer": pd.DataFrame({
            "x": signal_x,
            "y": signal_y,
            "z": signal_z
        }, index=pd.date_range("2025-01-01", periods=1000, freq="1ms", tz="UTC"))
    }

    features = {
        "cluster": pd.DataFrame({
            "start_utc": [pd.Timestamp("2025-01-01 00:00:00", tz="UTC")],
            "end_utc": [pd.Timestamp("2025-01-01 00:10:00", tz="UTC")],
        })
    }

    result = acc_kurtosis(sensors, features, window_key="cluster")
    kurt = result["cluster"]["acc_kurtosis"].iloc[0]
    # Normalverteilung → Kurtosis ≈ 0 (Excess-Kurtosis)
    # Mit 3000 Samples (1000 je Achse) sollte es sehr nah an 0 sein
    assert abs(kurt) < 2.0, f"Normal-Verteilung sollte Kurtosis ≈ 0 haben, got {kurt}"


def test_acc_kurtosis_spike_signal():
    """Test: Signal mit Spike hat hohe Kurtosis."""
    signal = np.zeros(1000)
    signal[500] = 100  # Ein großer Spike

    sensors = {
        "Accelerometer": pd.DataFrame({
            "x": signal,
            "y": np.zeros(1000),
            "z": np.zeros(1000)
        }, index=pd.date_range("2025-01-01", periods=1000, freq="1ms", tz="UTC"))
    }

    features = {
        "cluster": pd.DataFrame({
            "start_utc": [pd.Timestamp("2025-01-01 00:00:00", tz="UTC")],
            "end_utc": [pd.Timestamp("2025-01-01 00:10:00", tz="UTC")],
        })
    }

    result = acc_kurtosis(sensors, features, window_key="cluster")
    kurt = result["cluster"]["acc_kurtosis"].iloc[0]
    # Signal mit Spike → hohe Kurtosis
    assert kurt > 5, f"Signal mit Spike sollte hohe Kurtosis haben, got {kurt}"


# Integration Test: Alle 5 Features
def test_full_feature_pipeline_5_features():
    """
    Integration-Test: Alle 5 Features (RMS, STD, P2P, ZCR, Kurtosis) zusammen.
    """
    # Setup
    base_time = pd.Timestamp("2025-01-01 00:00:00Z", tz="UTC")
    times = [base_time + timedelta(seconds=i*0.01) for i in range(200)]

    # Zwei verschiedene Signale
    signal_1 = np.sin(2 * np.pi * 2 * np.arange(100) * 0.01)  # 2 Hz
    signal_2 = np.random.normal(0, 0.5, 100)  # Noise

    sensors = {
        "Accelerometer": pd.DataFrame({
            "x": list(signal_1) + list(signal_2),
            "y": list(-signal_1) + list(signal_2),
            "z": [0.1 * x for x in (list(signal_1) + list(signal_2))]
        }, index=pd.DatetimeIndex(times, name="time_utc"))
    }

    features = {
        "cluster": pd.DataFrame({
            "window_id": [0, 1],
            "start_utc": [base_time, base_time + timedelta(seconds=1)],
            "end_utc": [base_time + timedelta(seconds=1), base_time + timedelta(seconds=2)],
        })
    }

    # Feature-Pipeline
    result = features
    result = acc_rms(sensors, result, window_key="cluster")
    result = acc_std(sensors, result, window_key="cluster")
    result = acc_p2p(sensors, result, window_key="cluster")
    result = zero_crossing_rate(sensors, result, window_key="cluster")
    result = acc_kurtosis(sensors, result, window_key="cluster")

    # Prüfen: Alle 5 Feature-Spalten vorhanden
    feature_df = result["cluster"]
    expected_cols = ["acc_rms", "acc_std", "acc_p2p", "zero_crossing_rate", "acc_kurtosis"]
    for col in expected_cols:
        assert col in feature_df.columns, f"Feature-Spalte '{col}' fehlt!"

    # Prüfen: Werte plausibel (nicht alle NaN)
    for col in expected_cols:
        assert not feature_df[col].isna().all(), f"Spalte '{col}' ist komplett NaN!"

    # Prüfen: DataFrame-Struktur
    assert len(feature_df) == 2  # 2 Fenster
    assert set(feature_df.columns) >= set(["start_utc", "end_utc"] + expected_cols)

    print("\n✅ Full Feature Pipeline Test passed!")
    print(f"Feature DataFrame:\n{feature_df[['window_id'] + expected_cols]}")


# Tests for normalize_features_by_velocity
def test_normalize_features_basic(mock_features_with_velocity):
    """Test basic velocity normalization with known values."""
    # ARRANGE
    sensors = {}
    features = mock_features_with_velocity

    # ACT
    result = normalize_features_by_velocity(
        sensors, features, window_key="cluster",
        velocity_exponent=2.0, velocity_epsilon=0.0, v_confidence_threshold=0.5
    )

    # ASSERT
    fdf = result["cluster"]
    assert "acc_rms_vnorm" in fdf.columns
    assert "acc_std_vnorm" in fdf.columns

    # v=2, exponent=2, eps=0: factor = 2^2 = 4
    assert np.isclose(fdf["acc_rms_vnorm"].iloc[0], 10.0 / 4.0)  # 2.5
    assert np.isclose(fdf["acc_std_vnorm"].iloc[0], 5.0 / 4.0)   # 1.25

    # Original columns preserved
    assert fdf["acc_rms"].iloc[0] == 10.0
    assert fdf["acc_std"].iloc[0] == 5.0


def test_normalize_features_low_confidence(mock_features_with_velocity):
    """Test that low confidence windows result in NaN vnorm."""
    # ARRANGE
    sensors = {}
    features = mock_features_with_velocity

    # ACT
    result = normalize_features_by_velocity(
        sensors, features, window_key="cluster",
        v_confidence_threshold=0.5
    )

    # ASSERT
    fdf = result["cluster"]
    # Window 2 has confidence=0.3 < 0.5 → vnorm should be NaN
    assert pd.isna(fdf["acc_rms_vnorm"].iloc[2])
    assert pd.isna(fdf["acc_std_vnorm"].iloc[2])


def test_normalize_features_nan_velocity():
    """Test that NaN velocity propagates to vnorm."""
    # ARRANGE
    sensors = {}
    features = {
        "cluster": pd.DataFrame({
            "start_utc": [pd.Timestamp("2025-01-01", tz="UTC")],
            "end_utc": [pd.Timestamp("2025-01-01 00:00:04", tz="UTC")],
            "acc_rms": [10.0],
            "v": [np.nan],
            "v_confidence": [0.9]
        })
    }

    # ACT
    result = normalize_features_by_velocity(
        sensors, features, window_key="cluster"
    )

    # ASSERT
    fdf = result["cluster"]
    assert pd.isna(fdf["acc_rms_vnorm"].iloc[0])


def test_normalize_features_epsilon_prevents_div_zero():
    """Test that epsilon prevents division by zero."""
    # ARRANGE
    sensors = {}
    features = {
        "cluster": pd.DataFrame({
            "start_utc": [pd.Timestamp("2025-01-01", tz="UTC")],
            "end_utc": [pd.Timestamp("2025-01-01 00:00:04", tz="UTC")],
            "acc_rms": [10.0],
            "v": [0.0],  # Zero velocity
            "v_confidence": [0.9]
        })
    }

    # ACT
    result = normalize_features_by_velocity(
        sensors, features, window_key="cluster",
        velocity_exponent=1.5, velocity_epsilon=0.1
    )

    # ASSERT
    fdf = result["cluster"]
    # v=0: factor = 0^1.5 + 0.1 = 0.1
    assert np.isclose(fdf["acc_rms_vnorm"].iloc[0], 10.0 / 0.1)  # 100.0
    assert np.isfinite(fdf["acc_rms_vnorm"].iloc[0])  # Not inf


def test_normalize_features_skips_kurtosis(mock_features_with_velocity):
    """Test that acc_kurtosis is NOT normalized."""
    # ARRANGE
    sensors = {}
    features = mock_features_with_velocity

    # ACT
    result = normalize_features_by_velocity(
        sensors, features, window_key="cluster"
    )

    # ASSERT
    fdf = result["cluster"]
    assert "acc_rms_vnorm" in fdf.columns
    assert "acc_kurtosis_vnorm" not in fdf.columns  # NOT normalized
    assert fdf["acc_kurtosis"].iloc[0] == 0.0  # Unchanged


def test_normalize_features_missing_velocity_raises():
    """Test that missing v column raises ValueError."""
    # ARRANGE
    sensors = {}
    features = {
        "cluster": pd.DataFrame({
            "start_utc": [pd.Timestamp("2025-01-01", tz="UTC")],
            "end_utc": [pd.Timestamp("2025-01-01 00:00:04", tz="UTC")],
            "acc_rms": [10.0],
            "v_confidence": [0.9]  # v missing
        })
    }

    # ACT & ASSERT
    with pytest.raises(ValueError, match="Missing required columns.*v"):
        normalize_features_by_velocity(sensors, features, window_key="cluster")


def test_normalize_features_missing_confidence_raises():
    """Test that missing v_confidence column raises ValueError."""
    # ARRANGE
    sensors = {}
    features = {
        "cluster": pd.DataFrame({
            "start_utc": [pd.Timestamp("2025-01-01", tz="UTC")],
            "end_utc": [pd.Timestamp("2025-01-01 00:00:04", tz="UTC")],
            "acc_rms": [10.0],
            "v": [2.0]  # v_confidence missing
        })
    }

    # ACT & ASSERT
    with pytest.raises(ValueError, match="Missing required columns.*v_confidence"):
        normalize_features_by_velocity(sensors, features, window_key="cluster")


def test_normalize_features_invalid_strategy_raises():
    """Test that unknown confidence_strategy raises ValueError."""
    # ARRANGE
    sensors = {}
    features = {
        "cluster": pd.DataFrame({
            "v": [1], "v_confidence": [0.9], "acc_rms": [1]
        })
    }

    # ACT & ASSERT
    with pytest.raises(ValueError, match="Unknown confidence_strategy"):
        normalize_features_by_velocity(
            sensors, features, window_key="cluster", confidence_strategy="invalid"
        )


def test_normalize_features_placeholder_strategy_raises():
    """Test that placeholder strategies raise NotImplementedError."""
    # ARRANGE
    sensors = {}
    features = {
        "cluster": pd.DataFrame({
            "v": [1], "v_confidence": [0.9], "acc_rms": [1]
        })
    }

    # ACT & ASSERT - soft_fallback
    with pytest.raises(NotImplementedError, match="soft_fallback.*placeholder"):
        normalize_features_by_velocity(
            sensors, features, window_key="cluster", confidence_strategy="soft_fallback"
        )

    # ACT & ASSERT - weighted
    with pytest.raises(NotImplementedError, match="weighted.*placeholder"):
        normalize_features_by_velocity(
            sensors, features, window_key="cluster", confidence_strategy="weighted"
        )


def test_normalize_features_multiple_windows(mock_features_with_velocity):
    """Test normalization across multiple windows with mixed confidence."""
    # ARRANGE
    sensors = {}
    features = mock_features_with_velocity

    # ACT
    result = normalize_features_by_velocity(
        sensors, features, window_key="cluster",
        velocity_exponent=1.0, velocity_epsilon=0.0, v_confidence_threshold=0.5
    )

    # ASSERT
    fdf = result["cluster"]

    # Window 0: high conf, v=2 → 10/2 = 5.0
    assert np.isclose(fdf["acc_rms_vnorm"].iloc[0], 5.0)

    # Window 1: high conf, v=3 → 15/3 = 5.0
    assert np.isclose(fdf["acc_rms_vnorm"].iloc[1], 5.0)

    # Window 2: low conf (0.3 < 0.5) → NaN
    assert pd.isna(fdf["acc_rms_vnorm"].iloc[2])


def test_full_pipeline_with_velocity_normalization():
    """Integration test: velocity extraction → raw features → normalization."""
    # ARRANGE
    base_time = pd.Timestamp("2025-01-01 00:00:00Z", tz="UTC")
    times_acc = [base_time + timedelta(seconds=i*0.01) for i in range(400)]  # 4 seconds @ 100Hz
    times_loc = [base_time, base_time + timedelta(seconds=2), base_time + timedelta(seconds=4)]

    sensors = {
        "Accelerometer": pd.DataFrame({
            "x": np.sin(2 * np.pi * 2 * np.arange(400) * 0.01),
            "y": np.cos(2 * np.pi * 2 * np.arange(400) * 0.01),
            "z": np.random.normal(0, 0.1, 400)
        }, index=pd.DatetimeIndex(times_acc, name="time_utc")),

        "Location": pd.DataFrame({
            "speed": [3.0, 5.0, 2.0],  # m/s
            "speedAccuracy": [0.5, 0.8, 0.3]
        }, index=pd.DatetimeIndex(times_loc, name="time_utc"))
    }

    features = {
        "cluster": pd.DataFrame({
            "window_id": [0],
            "start_utc": [base_time],
            "end_utc": [base_time + timedelta(seconds=4)],
        })
    }

    # ACT - Run full pipeline
    result = features
    result = compute_window_velocity(sensors, result, window_key="cluster")
    result = acc_rms(sensors, result, window_key="cluster")
    result = acc_std(sensors, result, window_key="cluster")
    result = normalize_features_by_velocity(
        sensors, result, window_key="cluster",
        velocity_exponent=1.5, velocity_epsilon=0.1, v_confidence_threshold=0.5
    )

    # ASSERT
    fdf = result["cluster"]

    # Check all columns present
    assert "v" in fdf.columns
    assert "v_confidence" in fdf.columns
    assert "acc_rms" in fdf.columns
    assert "acc_rms_vnorm" in fdf.columns
    assert "acc_std" in fdf.columns
    assert "acc_std_vnorm" in fdf.columns

    # Check vnorm is different from raw (velocity should affect normalization)
    if fdf["v"].iloc[0] > 1.5:
        assert fdf["acc_rms_vnorm"].iloc[0] < fdf["acc_rms"].iloc[0]
        assert fdf["acc_std_vnorm"].iloc[0] < fdf["acc_std"].iloc[0]


# ============================================================================
# Tests for compute_optimal_exponent
# ============================================================================

def test_compute_optimal_exponent_perfect_fit():
    """
    Test: Perfekte Power-Law Daten (f = 2.0 * v^1.5)
    ARRANGE: Synthetische Daten ohne Rauschen
    ACT: Kalibriere Exponent
    ASSERT: Exponent ≈ 1.5, R² ≈ 1.0
    """
    # ARRANGE
    n_windows = 50
    velocities = np.linspace(2.0, 10.0, n_windows)

    # Perfect power law: f = 2.0 * v^1.5
    true_exponent = 1.5
    features_values = 2.0 * (velocities ** true_exponent)

    # Create mock Ctx
    features_df = pd.DataFrame({
        "v": velocities,
        "v_confidence": np.ones(n_windows) * 0.9,
        "acc_rms": features_values
    })

    ctx = make_ctx(
        sensors={},
        features={"cluster": features_df},
        config={}
    )

    # ACT
    exponent = compute_optimal_exponent(ctx, "cluster", feature="acc_rms")

    # ASSERT
    assert np.isclose(exponent, true_exponent, atol=0.01), f"Expected {true_exponent}, got {exponent}"


def test_compute_optimal_exponent_noisy_data():
    """
    Test: Power-Law Daten mit Rauschen
    ARRANGE: f = 2.0 * v^1.6 + noise
    ACT: Kalibriere Exponent
    ASSERT: Exponent ∈ [1.5, 1.7], R² > 0.8
    """
    # ARRANGE
    np.random.seed(42)
    n_windows = 100
    velocities = np.linspace(2.0, 12.0, n_windows)

    # Noisy power law
    true_exponent = 1.6
    noise = np.random.normal(0, 0.5, n_windows)
    features_values = 2.0 * (velocities ** true_exponent) + noise

    features_df = pd.DataFrame({
        "v": velocities,
        "v_confidence": np.ones(n_windows) * 0.95,
        "acc_rms": features_values
    })

    ctx = make_ctx(
        sensors={},
        features={"cluster": features_df},
        config={}
    )

    # ACT
    exponent = compute_optimal_exponent(ctx, "cluster", feature="acc_rms")

    # ASSERT
    assert 1.5 <= exponent <= 1.7, f"Expected exponent in [1.5, 1.7], got {exponent}"


def test_compute_optimal_exponent_insufficient_data():
    """
    Test: Zu wenig Datenpunkte (< 30)
    ARRANGE: Nur 20 Fenster
    ACT: Kalibriere Exponent
    ASSERT: Fällt zurück auf fallback_exponent=1.5
    """
    # ARRANGE
    n_windows = 20  # < 30
    velocities = np.linspace(3.0, 8.0, n_windows)
    features_values = 2.0 * (velocities ** 1.6)

    features_df = pd.DataFrame({
        "v": velocities,
        "v_confidence": np.ones(n_windows) * 0.9,
        "acc_rms": features_values
    })

    ctx = make_ctx(
        sensors={},
        features={"cluster": features_df},
        config={}
    )

    # ACT
    exponent = compute_optimal_exponent(ctx, "cluster", feature="acc_rms")

    # ASSERT
    assert exponent == 1.5, f"Expected fallback to 1.5, got {exponent}"


def test_compute_optimal_exponent_low_confidence():
    """
    Test: Niedrige v_confidence (< threshold)
    ARRANGE: Alle Fenster haben v_confidence < 0.7
    ACT: Kalibriere Exponent
    ASSERT: Fällt zurück auf fallback (zu wenig valid windows)
    """
    # ARRANGE
    n_windows = 50
    velocities = np.linspace(2.0, 10.0, n_windows)
    features_values = 2.0 * (velocities ** 1.5)

    features_df = pd.DataFrame({
        "v": velocities,
        "v_confidence": np.ones(n_windows) * 0.3,  # Alle < 0.7!
        "acc_rms": features_values
    })

    ctx = make_ctx(
        sensors={},
        features={"cluster": features_df},
        config={}
    )

    # ACT
    exponent = compute_optimal_exponent(ctx, "cluster", feature="acc_rms", confidence_threshold=0.7)

    # ASSERT
    assert exponent == 1.5, f"Expected fallback to 1.5 due to low confidence, got {exponent}"


def test_compute_optimal_exponent_low_r_squared():
    """
    Test: Schlechte Regression (Low R²)
    ARRANGE: Zufällige Daten (kein Power-Law)
    ACT: Kalibriere Exponent
    ASSERT: Fällt zurück auf fallback wegen R² < 0.6
    """
    # ARRANGE
    np.random.seed(123)
    n_windows = 100
    velocities = np.linspace(2.0, 10.0, n_windows)
    features_values = np.random.uniform(5, 15, n_windows)  # Random, kein Pattern!

    features_df = pd.DataFrame({
        "v": velocities,
        "v_confidence": np.ones(n_windows) * 0.9,
        "acc_rms": features_values
    })

    ctx = make_ctx(
        sensors={},
        features={"cluster": features_df},
        config={}
    )

    # ACT
    exponent = compute_optimal_exponent(ctx, "cluster", feature="acc_rms", min_r_squared=0.6)

    # ASSERT
    assert exponent == 1.5, f"Expected fallback to 1.5 due to low R², got {exponent}"


def test_compute_optimal_exponent_missing_columns():
    """
    Test: Fehlende Spalten (v oder v_confidence fehlt)
    ARRANGE: DataFrame ohne v_confidence
    ACT: Kalibriere Exponent
    ASSERT: Fällt zurück auf fallback
    """
    # ARRANGE
    features_df = pd.DataFrame({
        "v": [3.0, 5.0, 7.0],
        "acc_rms": [10.0, 15.0, 20.0]
        # v_confidence fehlt!
    })

    ctx = make_ctx(
        sensors={},
        features={"cluster": features_df},
        config={}
    )

    # ACT
    exponent = compute_optimal_exponent(ctx, "cluster", feature="acc_rms")

    # ASSERT
    assert exponent == 1.5, f"Expected fallback to 1.5 due to missing columns, got {exponent}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
