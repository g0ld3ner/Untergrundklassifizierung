# tests/test_sensors.py
import pytest
import pandas as pd
from typing import Iterable, cast
from untergrund.shared import sensors as S


def df(y: Iterable[int]) -> pd.DataFrame:
    return pd.DataFrame({"y": list(y)})



# -------------------- Transform: Basis & Broadcast --------------------

def test_transform_broadcast_single_and_dict_with_sensor_name_forwarding():
    @S.transform_all_sensors
    def inc(x: pd.DataFrame, *, sensor_name: str | None = None, c: int = 1) -> pd.DataFrame:
        out = x.copy()
        out["y"] = out["y"] + c
        out.attrs["seen_name"] = sensor_name
        return out

    # Einzelwert
    out_single = cast(pd.DataFrame, inc.with_kwargs(c=5)(df([0, 1])))
    assert out_single["y"].tolist() == [5, 6]
    # Bei Einzelwerten wird sensor_name=None gesetzt (bewusst)
    assert getattr(out_single, "attrs").get("seen_name") is None

    # Dict-Broadcast
    sensors = {"s1": df([0]), "s2": df([10, 20])}
    out_dict = cast(dict[str, pd.DataFrame], inc.with_kwargs(c=2)(sensors))
    assert out_dict["s1"]["y"].tolist() == [2]
    assert out_dict["s2"]["y"].tolist() == [12, 22]
    # Name wird pro Key durchgereicht
    assert getattr(out_dict["s1"], "attrs")["seen_name"] == "s1"
    assert getattr(out_dict["s2"], "attrs")["seen_name"] == "s2"


# -------------------- select(): include/exclude/regex/predicate -------

def test_select_include_exclude_regex_predicate_applies_only_on_dicts():
    @S.transform_all_sensors
    def mark(x: pd.DataFrame, *, sensor_name: str | None = None, tag: str = "X") -> pd.DataFrame:
        out = x.copy()
        out["tag"] = tag
        return out

    sensors = {
        "A": df([1]),
        "B1": df([2, 3]),
        "B2": df([4]),
        "C": df([5]),
    }

    # Regex-Selektor: nur B*
    step = mark.select(regex=r"^B").with_kwargs(tag="B")
    out = cast(dict[str, pd.DataFrame], step(sensors))
    assert "tag" not in out["A"].columns
    assert out["B1"]["tag"].tolist() == ["B", "B"]
    assert out["B2"]["tag"].tolist() == ["B"]
    assert "tag" not in out["C"].columns

    # Predicate: nur DataFrames mit mehr als 1 Zeile
    step2 = mark.select(predicate=lambda n, v: len(v) > 1).with_kwargs(tag="LONG")
    out2 = cast(dict[str, pd.DataFrame], step2(sensors))
    assert "tag" not in out2["A"].columns
    assert out2["B1"]["tag"].tolist() == ["LONG", "LONG"]
    assert "tag" not in out2["B2"].columns
    assert "tag" not in out2["C"].columns

    # Selektor bei Einzelwerten: wird ignoriert (bewusste Semantik)
    single = cast(pd.DataFrame, mark.select(include=["NOPE"]).with_kwargs(tag="IGNORED")(df([9])))
    assert single["tag"].tolist() == ["IGNORED"]


# -------------------- with_kwargs(): Validierung & defensive Kopie -----

def test_with_kwargs_rejects_setting_sensor_name():
    @S.transform_all_sensors
    def core(x: pd.DataFrame, *, sensor_name: str | None = None, k: int = 0) -> pd.DataFrame:
        return x

    with pytest.raises(TypeError, match=r"sensor_name"):
        _ = core.with_kwargs(sensor_name="evil")


def test_with_kwargs_unknown_key_raises_without_varkw():
    @S.transform_all_sensors
    def core(x: pd.DataFrame, *, sensor_name: str | None = None, a: int = 1) -> pd.DataFrame:
        return x

    with pytest.raises(TypeError, match=r"Unknown|Invalid kwargs"):
        _ = core.with_kwargs(b=2)


def test_with_kwargs_allows_unknown_when_core_has_varkw():
    @S.transform_all_sensors
    def core(x: pd.DataFrame, *, sensor_name: str | None = None, **kw) -> pd.DataFrame:
        # nutzt kw nicht; testet nur, dass Validierung durchgeht
        return x

    # darf durchgehen, weil **kw in der Core-Signatur ist
    step = core.with_kwargs(foo=123, bar="x")
    out = cast(pd.DataFrame, step(df([1])))
    assert out["y"].tolist() == [1]


def test_with_kwargs_defensive_copy_shallow():
    @S.transform_all_sensors
    def drop_cols(x: pd.DataFrame, *, sensor_name: str | None = None, cols: list[str] | None = None) -> pd.DataFrame:
        out = x.copy()
        for c in cols or []:
            if c in out.columns:
                del out[c]
        return out

    original = ["y"]          # wird später mutiert
    step = drop_cols.with_kwargs(cols=original)
    original.append("nonexistent")  # sollte im Step NICHT ankommen (shallow copy beim Binden)

    out = cast(pd.DataFrame, step(pd.DataFrame({"y": [1], "z": [2]})))
    assert list(out.columns) == ["z"]


# -------------------- Inspector: Tap/Side-Effects ----------------------

def test_inspector_select_and_with_kwargs_and_name_forwarding():
    calls: list[tuple[str | None, int]] = []

    @S.inspect_all_sensors
    def tap(x: pd.DataFrame, *, sensor_name: str | None = None, add: int = 0) -> None:
        calls.append((sensor_name, int(x["y"].sum()) + add))
        return None

    sensors = {"s1": df([1, 2]), "s2": df([3])}
    step = tap.select(include=["s2"]).with_kwargs(add=5)
    result = step(sensors)

    # Rückgabe ist immer None (Tap)
    assert result is None
    # Nur s2 wurde inspiziert, add=5 wurde gebunden
    assert calls == [("s2", 3 + 5)]


def test_inspector_select_ignored_on_single_value():
    seen: list[str | None] = []

    @S.inspect_all_sensors
    def tap(x: pd.DataFrame, *, sensor_name: str | None = None) -> None:
        seen.append(sensor_name)

    _ = tap.select(include=["NOPE"])(df([7]))  # Selektor ignoriert, weil Einzelwert
    assert seen == [None]


# -------------------- Verträge & Meta-API ------------------------------

def test_sensor_name_must_be_keyword_only_enforced_on_decorate():
    # Fehler: sensor_name ist positional → Decorator muss fehlschlagen
    def bad(x: pd.DataFrame, sensor_name, *, k: int = 0) -> pd.DataFrame:
        return x

    with pytest.raises(TypeError, match=r"sensor_name.*keyword-only"):
        _ = S.transform_all_sensors(bad)


def test_core_attr_is_original_function_and_survives_with_kwargs_and_select():
    @S.transform_all_sensors
    def core_fn(x: pd.DataFrame, *, sensor_name: str | None = None, k: int = 0) -> pd.DataFrame:
        return x

    base_core = core_fn.core
    assert callable(base_core)

    w = core_fn.with_kwargs(k=1)
    s = core_fn.select(include=["foo"])

    # .core sollte die ursprüngliche Kernfunktion bleiben
    assert w.core is base_core
    assert s.core is base_core
