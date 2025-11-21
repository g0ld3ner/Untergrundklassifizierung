import pandas as pd
import numpy as np
import pytest
from datetime import datetime, timedelta

from untergrund.runners.features import zero_crossing_rate, acc_kurtosis, acc_rms, acc_std, acc_p2p

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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
