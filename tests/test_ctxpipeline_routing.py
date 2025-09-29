from typing import cast, Any
from untergrund import Ctx, CtxPipeline
from dataclasses import replace
import pandas as pd

# sentinel values for unchanged fields
S_META = object()
S_FEATURES = object()
S_PREDS = object()
S_CONFIG = object()
S_ARTIFACTS = object()

# mini test config
def make_tiny_ctx():
    df = pd.DataFrame({"time":[1,2,3], "x":[0.0,0.1,0.0], "y":[0.0,0.0,0.1], "z":[9.8,9.7,9.81]})
    sensors = {"acc": df}
    return Ctx(sensors=sensors,
                meta=cast(dict[str, Any], S_META),
                features=cast(pd.DataFrame, S_FEATURES),
                preds=cast(pd.Series, S_PREDS),
                config=cast(dict[str, Any], S_CONFIG),
                artifacts=cast(dict[str, Any], S_ARTIFACTS)
                )

# mini transform function
def add_flag_to_acc(sensor_dict: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    out = {k: v.copy() for k, v in sensor_dict.items()}
    out["acc"]["flag"] = True # flag als neue Spalte mit True-Werten
    return out
# expected columns after mini transform function
expected_cols = {"time","x","y","z","flag"}

# mini combine function
def combine_sensors_and_config(sensor_dict: dict[str, pd.DataFrame], config: dict[str, Any]) -> dict[str, pd.DataFrame]:
    out = {k: v.copy() for k, v in sensor_dict.items()}
    for _, df in out.items():
        df["flag"] = config.get("flag", False) # neue Spalte mit dem Wert aus config["flag"]
    return out


##### Test Functions for CtxPipeline routing #####
def test_ctx_pipeline_single_source_routing():
    """Testet die Routing-Fähigkeiten von CtxPipeline.add() mit source = dest."""
    # create a tiny context
    ctx = make_tiny_ctx()
    pipe = CtxPipeline()
    pipe.add(add_flag_to_acc, source="sensors") # source = dest (= "sensors")
    # run the pipeline
    final_ctx = pipe(ctx)

    ### Assertions to verify the routing
    # Check that final_ctx is a new Ctx object with updated sensors
    assert isinstance(final_ctx, Ctx)
    assert final_ctx is not ctx  
    assert final_ctx.sensors is not ctx.sensors
    assert final_ctx.sensors["acc"] is not ctx.sensors["acc"]  
    # Check that the "acc" sensor has the new "flag" column
    assert isinstance(final_ctx.sensors["acc"], pd.DataFrame)
    assert set(final_ctx.sensors["acc"].columns) == expected_cols
    assert len(final_ctx.sensors["acc"]) == len(ctx.sensors["acc"])
    assert final_ctx.sensors["acc"]["flag"].all()
    # Check that the "flag" column is not in the original ctx. (leak check)
    assert "flag" not in ctx.sensors["acc"].columns  
    # Check that unchanged fields are the same object
    assert final_ctx.meta is ctx.meta
    assert final_ctx.features is ctx.features
    assert final_ctx.preds is ctx.preds
    assert final_ctx.config is ctx.config
    assert final_ctx.artifacts is ctx.artifacts


def test_ctx_pipeline_single_source_to_other_dest_routing():
    """Testet die Routing-Fähigkeiten von CtxPipeline.add() mit source != dest."""
    # create a tiny context
    ctx = make_tiny_ctx()
    pipe = CtxPipeline()
    pipe.add(add_flag_to_acc, source="sensors", dest="artifacts") # source != dest ("sensors" -> "artifacts")
    # run the pipeline
    final_ctx = pipe(ctx)

    ### Assertions to verify the routing
    # Check that final_ctx is a new Ctx object with updated artifacts
    assert isinstance(final_ctx, Ctx)
    assert final_ctx is not ctx  
    assert final_ctx.artifacts is not ctx.artifacts
    # Check that the "acc" artifact has the new "flag" column
    assert isinstance(final_ctx.sensors["acc"], pd.DataFrame)
    assert isinstance(final_ctx.artifacts["acc"], pd.DataFrame)
    assert set(final_ctx.artifacts["acc"].columns) == expected_cols
    assert final_ctx.artifacts["acc"]["flag"].all()
    # Check that the "flag" column is not in the original ctx. (leak check)
    assert "flag" not in ctx.sensors["acc"].columns 
    # Check that unchanged fields are the same object
    assert final_ctx.sensors is ctx.sensors
    assert final_ctx.sensors["acc"] is ctx.sensors["acc"]
    assert final_ctx.meta is ctx.meta
    assert final_ctx.features is ctx.features
    assert final_ctx.preds is ctx.preds
    assert final_ctx.config is ctx.config
    
def test_ctx_pipeline_multi_source_to_other_dest_routing():
    """Testet die Routing-Fähigkeiten von CtxPipeline.add() mit mehreren Quellen und einem anderen Ziel."""
    # create a tiny context
    ctx = make_tiny_ctx()
    # config überschreiben
    config={"flag": True}
    ctx = replace(ctx, config=config)
    # create a pipeline
    pipe = CtxPipeline()
    pipe.add(combine_sensors_and_config, source=["sensors", "config"], dest="artifacts") # ["sensors", "config"] -> "artifacts"
    # run the pipeline
    final_ctx = pipe(ctx)

    ### Assertions to verify the routing
    # Check that final_ctx is a new Ctx object with updated artifacts
    assert isinstance(final_ctx, Ctx)
    assert final_ctx is not ctx
    assert final_ctx.artifacts is not ctx.artifacts
    # Check that the "acc" artifact has the new "flag" column
    assert isinstance(final_ctx.artifacts["acc"], pd.DataFrame)
    assert set(final_ctx.artifacts["acc"].columns) == expected_cols
    assert final_ctx.artifacts["acc"]["flag"].all()
    # Check that the source is unchanged + leak check
    assert isinstance(final_ctx.sensors["acc"], pd.DataFrame)
    assert final_ctx.sensors["acc"] is ctx.sensors["acc"]
    assert final_ctx.artifacts["acc"] is not ctx.sensors["acc"]
    assert "flag" not in final_ctx.sensors["acc"].columns
    # Check that the config is unchanged
    assert isinstance(final_ctx.config, dict)
    assert final_ctx.config is ctx.config
    assert final_ctx.config == {"flag": True}
    # Check that unchanged fields are the same object
    assert final_ctx.sensors is ctx.sensors
    assert final_ctx.meta is ctx.meta
    assert final_ctx.features is ctx.features
    assert final_ctx.preds is ctx.preds
    assert final_ctx.config is ctx.config


def test_ctx_pipeline_tap_immutability():
    """Testet, dass CtxPipeline.tap() den Ctx nicht verändert."""
    # create a tiny context
    ctx = make_tiny_ctx()
    # create a pipeline with a tap step
    pipe = CtxPipeline()

    def tap_func(s: dict[str, pd.DataFrame]) -> None:
        # try to mutate the input dict (should not affect the original ctx)
        s["acc"]["flag"] = True
    pipe.tap(tap_func, source="sensors")
    # run the pipeline
    final_ctx = pipe(ctx)

    ### Assertions to verify immutability
    # Check that final_ctx IS the Ctx object (immutability)
    assert isinstance(final_ctx, Ctx)
    assert final_ctx is ctx
    # Check that the sensors reference is the same (no changes)
    assert final_ctx.sensors is ctx.sensors
    assert final_ctx.sensors["acc"].equals(ctx.sensors["acc"])
    # Check that the "flag" column is not in the original or final ctx. (leak check)
    assert "flag" not in ctx.sensors["acc"].columns  
    assert "flag" not in final_ctx.sensors["acc"].columns 
    # Check that untouched fields are the same object
    assert final_ctx.meta is ctx.meta
    assert final_ctx.features is ctx.features
    assert final_ctx.preds is ctx.preds
    assert final_ctx.config is ctx.config
    assert final_ctx.artifacts is ctx.artifacts
    