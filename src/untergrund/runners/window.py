from ..context import Ctx
from ..pipeline import CtxPipeline
import pandas as pd

def run_window(ctx: "Ctx") -> "Ctx":
    pipeline = CtxPipeline()
    # Add the windowing step to the pipeline here
    return pipeline(ctx)

def windowing() -> pd.DataFrame:
    ... # Implementation of the windowing logic 