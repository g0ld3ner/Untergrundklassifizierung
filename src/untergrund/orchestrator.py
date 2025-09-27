from .stages import Stage
from .context import Ctx
from .runners.ingest import run_ingest
from .runners.select import run_select
from .runners.preprocess import run_preprocess
from .runners.features import run_features
from .runners.classify import run_classify
from .runners.export import run_export

STAGE_FUNCS = {
    Stage.INGEST: run_ingest,
    Stage.SELECT: run_select,
    Stage.PREPROCESS: run_preprocess,
    Stage.FEATURES: run_features,
    Stage.CLASSIFY: run_classify,
    Stage.EXPORT: run_export,
}

def run_stages(ctx: "Ctx") -> "Ctx":
    for st in Stage:
        ctx = STAGE_FUNCS[st](ctx) 
    return ctx