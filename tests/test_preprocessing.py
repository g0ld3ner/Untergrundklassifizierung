import pandas as pd
import numpy as np
import pytest

from untergrund.runners.preprocess import time_to_index, handle_nat_in_index, sort_sensors_by_time_index, group_duplicate_timeindex, validate_basic_preprocessing


#---KI generierte Tests zu time_to_index---#
def test_time_to_index_basic_ns_to_utc_index():
    # 2024-01-01 00:00:00Z und +1 Minute in Nanosekunden
    df = pd.DataFrame({
        "time": [1704067200000000000, 1704067260000000000],
        "value": [10, 20],
    })
    out = time_to_index.core(df)

    expected_idx = pd.to_datetime(
        ["2024-01-01 00:00:00Z", "2024-01-01 00:01:00Z"], utc=True
    )
    expected_idx = pd.DatetimeIndex(expected_idx, name="time_utc")

    assert isinstance(out.index, pd.DatetimeIndex)
    assert out.index.equals(expected_idx)  # prüft inkl. UTC-TZ & Indexname
    assert "time" not in out.columns
    assert list(out["value"]) == [10, 20]


def test_time_to_index_does_not_mutate_input_df():
    df = pd.DataFrame({"time": [1704067200000000000], "v": [1]})
    df_before = df.copy(deep=True)
    _ = time_to_index.core(df)
    # Input bleibt unverändert (keine In-Place-Operationen)
    assert df.equals(df_before)


def test_time_to_index_missing_time_column_raises():
    df = pd.DataFrame({"v": [1, 2]})
    with pytest.raises(ValueError):
        _ = time_to_index.core(df)
#--- ---#

#---KI generierte Tests zu handle_nat_in_index---#
def test_no_nat_early_exit_identity():
    idx = pd.to_datetime(["2025-01-01T00:00:00Z","2025-01-01T00:00:01Z"], utc=True)
    df = pd.DataFrame({"v":[1,2]}, index=pd.DatetimeIndex(idx, name="time_utc"))
    out = handle_nat_in_index.core(df)
    assert out is df

def test_drop_and_gap_detection():
    idx = pd.DatetimeIndex([
        pd.NaT,
        pd.to_datetime("2025-01-01T00:00:00Z", utc=True),
        pd.NaT, pd.NaT,                # Cluster Länge 2
        pd.to_datetime("2025-01-01T00:00:01Z", utc=True)
    ], name="time_utc")
    df = pd.DataFrame({"v":[9,1,8,7,2]}, index=idx)
    out = handle_nat_in_index.core(df, gap_len=2)
    assert out.index.isna().sum() == 0
    assert list(out["v"]) == [1,2] 
#--- ---#

#---KI generierte Tests zu sort_sensors_by_time_index---#
def test_already_sorted_no_change():
    t = pd.to_datetime(["2025-01-01 00:00:00Z", "2025-01-01 00:00:01Z", "2025-01-01 00:00:02Z"])
    df = pd.DataFrame({"v": [1, 2, 3]}, index=pd.DatetimeIndex(t, name="time_utc"))
    out = sort_sensors_by_time_index.core(df)
    # Früh-Exit → gleiches Objekt (idempotent & kein Copy-Overhead)
    assert out is df
    assert out.index.is_monotonic_increasing
    assert out.index.name == "time_utc"


def test_unsorted_gets_sorted_stably():
    # Duplikate von t2, unsortiert (t2a vor t1 vor t2b)
    t1 = pd.Timestamp("2025-01-01 00:00:01Z")
    t2a = pd.Timestamp("2025-01-01 00:00:02Z")
    t2b = pd.Timestamp("2025-01-01 00:00:02Z")
    df = pd.DataFrame({"v": ["a", "b", "c"]},
                      index=pd.DatetimeIndex([t2a, t1, t2b], name="time_utc"))
    out = sort_sensors_by_time_index.core(df)
    # Erwartet: [t1, t2a, t2b] und stabile Reihenfolge für gleiche Timestamps ("a" vor "c")
    assert list(out.index) == [t1, t2a, t2b]
    assert list(out["v"]) == ["b", "a", "c"]
    assert out.index.is_monotonic_increasing


def test_nat_goes_last():
    t1 = pd.Timestamp("2025-01-01 00:00:00Z")
    t2 = pd.Timestamp("2025-01-01 00:00:01Z")
    nat = pd.NaT
    # absichtlich unsortiert mit NaT
    df = pd.DataFrame({"v": [1, 99, 2]},
                      index=pd.DatetimeIndex([nat, t2, t1], name="time_utc"))
    out = sort_sensors_by_time_index.core(df)
    # NaT muss ans Ende wandern (na_position="last")
    assert list(out.index) == [t1, t2, nat]
    assert pd.isna(out.index[-1])


def test_empty_df_returns_unchanged():
    df = pd.DataFrame({"v": []}, index=pd.DatetimeIndex([], name="time_utc"))
    out = sort_sensors_by_time_index.core(df)
    assert out is df
    assert len(out) == 0


def test_not_datetime_index_raises():
    df = pd.DataFrame({"v": [1, 2, 3]})  # RangeIndex
    with pytest.raises(ValueError):
        sort_sensors_by_time_index.core(df)
#--- ---#

#---KI generierte Tests zu sort_sensors_by_time_index---#
def test_group_no_duplicates_idempotent():
    t = pd.to_datetime(["2025-01-01 00:00:00Z", "2025-01-01 00:00:01Z"], utc=True)
    df = pd.DataFrame({"x": [1.0, 2.0], "label": ["a", "b"]},
                      index=pd.DatetimeIndex(t, name="time_utc"))
    out = group_duplicate_timeindex.core(df)
    # Keine Duplikate → identisches Objekt
    assert out is df
    assert out.index.is_unique
    assert list(out.columns) == ["x", "label"]


def test_group_numeric_median_non_numeric_first_incl_bool():
    # Duplikat auf t1 → numeric: median, non-numeric (inkl. bool): first
    t = pd.to_datetime(["2025-01-01 00:00:01Z",
                        "2025-01-01 00:00:01Z",
                        "2025-01-01 00:00:02Z"], utc=True)
    df = pd.DataFrame(
        {
            "a": [1.0, 3.0, 10.0],       # numeric → median = 2.0
            "b": [10, 30, 40],           # numeric → median = 20.0
            "flag": [True, False, True], # bool → first = True
            "label": ["first", "second", "keep"]  # non-numeric → first = "first"
        },
        index=pd.DatetimeIndex(t, name="time_utc")
    )
    out = group_duplicate_timeindex.core(df)
    assert out.index.is_unique
    # Gruppe auf t=...01Z wurde reduziert
    row = out.loc[pd.to_datetime("2025-01-01 00:00:01Z", utc=True)]
    assert float(row["a"]) == 2.0
    assert float(row["b"]) == 20.0
    assert bool(row["flag"]) is True
    assert str(row["label"]) == "first"
    # Spaltenreihenfolge bleibt erhalten
    assert list(out.columns) == ["a", "b", "flag", "label"]


def test_group_nat_is_deduplicated_with_dropna_false():
    # Zwei NaT-Zeilen + eine normale → mit dropna=False werden NaT zu einer Gruppe verdichtet
    idx = pd.DatetimeIndex([pd.NaT,
                            pd.NaT,
                            pd.to_datetime("2025-01-01 00:00:00Z", utc=True)],
                           name="time_utc")
    df = pd.DataFrame({"x": [1.0, 3.0, 5.0],
                       "s": ["u", "v", "w"],
                       "flag": [True, False, True]}, index=idx)
    out = group_duplicate_timeindex.core(df)
    assert out.index.is_unique
    # Genau ein NaT-Eintrag bleibt
    assert pd.isna(out.index[-1])
    # numeric median der NaT-Gruppe: (1.0, 3.0) -> 2.0
    assert float(out.loc[pd.NaT, "x"]) == 2.0
    # non-numeric first innerhalb der NaT-Gruppe
    assert out.loc[pd.NaT, "s"] == "u"
    assert bool(out.loc[pd.NaT, "flag"]) is True


def test_group_rowcount_matches_expected():
    # Drei Zeilen, davon zwei dupliziert auf t1 → eine Zeile weniger
    t = pd.to_datetime(["2025-01-01 00:00:01Z",
                        "2025-01-01 00:00:01Z",
                        "2025-01-01 00:00:02Z"], utc=True)
    df = pd.DataFrame({"v": [1, 2, 3]},
                      index=pd.DatetimeIndex(t, name="time_utc"))
    out = group_duplicate_timeindex.core(df)
    assert out.shape[0] == 2
    assert out.index.is_unique
#--- ---#

#---KI generierte Tests zu validate_basic_preprocessing---#
def test_valid_passes_and_prints_info(capsys):
    idx = pd.date_range("2025-01-01", periods=5, freq="s", tz="UTC").set_names(["time_utc"])
    df = pd.DataFrame({"x": np.arange(5, dtype=float)}, index=idx)
    out = validate_basic_preprocessing.core(df, sensor_name="acc")
    assert out is df
    assert "passed all basic preprocessing validations" in capsys.readouterr().out


def test_index_name_none_is_set_and_informs(capsys):
    idx = pd.date_range("2025-01-01", periods=3, freq="s", tz="UTC").set_names([None])
    df = pd.DataFrame({"x": np.arange(3, dtype=float)}, index=idx)
    validate_basic_preprocessing.core(df, sensor_name="gyro")
    assert df.index.name == "time_utc"
    assert "Set index name to 'time_utc'" in capsys.readouterr().out


def test_few_rows_info(capsys):
    idx = pd.date_range("2025-01-01", periods=3, freq="s", tz="UTC").set_names(["time_utc"])
    df = pd.DataFrame({"x": np.arange(3, dtype=float)}, index=idx)
    validate_basic_preprocessing.core(df, sensor_name="acc")
    assert "has only 3 rows, very little data" in capsys.readouterr().out


def test_empty_df_warning(capsys):
    idx = pd.DatetimeIndex([], tz="UTC", name="time_utc")
    df = pd.DataFrame(index=idx)
    validate_basic_preprocessing.core(df, sensor_name="acc")
    assert "is empty" in capsys.readouterr().out


def test_no_columns_warning(capsys):
    idx = pd.date_range("2025-01-01", periods=5, freq="s", tz="UTC").set_names(["time_utc"])
    df = pd.DataFrame(index=idx)  # keine Spalten
    validate_basic_preprocessing.core(df, sensor_name="acc")
    assert "has no columns" in capsys.readouterr().out


def test_non_datetime_index_raises():
    df = pd.DataFrame({"x": [1, 2, 3]})  # RangeIndex
    with pytest.raises(ValueError) as e:
        validate_basic_preprocessing.core(df, sensor_name="acc")
    assert "must be a DatetimeIndex" in str(e.value)


def test_naive_timezone_raises():
    idx = pd.date_range("2025-01-01", periods=3, freq="s")  # tz=None
    df = pd.DataFrame({"x": [1, 2, 3]}, index=idx)
    with pytest.raises(ValueError) as e:
        validate_basic_preprocessing.core(df, sensor_name="acc")
    assert "timezone-aware" in str(e.value)


def test_wrong_timezone_raises():
    idx = pd.date_range("2025-01-01", periods=3, freq="s", tz="Europe/Berlin")
    df = pd.DataFrame({"x": [1, 2, 3]}, index=idx)
    with pytest.raises(ValueError) as e:
        validate_basic_preprocessing.core(df, sensor_name="acc")
    assert "UTC timezone" in str(e.value)


def test_not_monotonically_increasing_raises():
    idx = pd.DatetimeIndex(
        ["2025-01-01 00:00:02+00:00", "2025-01-01 00:00:01+00:00", "2025-01-01 00:00:00+00:00"],
        tz="UTC",
        name="time_utc",
    )
    df = pd.DataFrame({"x": [1, 2, 3]}, index=idx)
    with pytest.raises(ValueError) as e:
        validate_basic_preprocessing.core(df, sensor_name="acc")
    assert "not monotonically increasing" in str(e.value)


def test_duplicates_in_index_raises():
    base = pd.date_range("2025-01-01 00:00:00", periods=3, freq="s", tz="UTC")
    idx = pd.DatetimeIndex([base[0], base[1], base[1]], name="time_utc")  # t1 doppelt
    df = pd.DataFrame({"x": [1, 2, 3]}, index=idx)
    with pytest.raises(ValueError) as e:
        validate_basic_preprocessing.core(df, sensor_name="acc")
    assert "duplicate time entries" in str(e.value)


def test_nat_in_index_raises():
    idx = pd.DatetimeIndex(
        ["2025-01-01 00:00:00+00:00", "NaT", "2025-01-01 00:00:02+00:00"],
        tz="UTC",
        name="time_utc",
    )
    df = pd.DataFrame({"x": [1, 2, 3]}, index=idx)
    with pytest.raises(ValueError) as e:
        validate_basic_preprocessing.core(df, sensor_name="acc")
    assert "NaT" in str(e.value)
#--- ---#
