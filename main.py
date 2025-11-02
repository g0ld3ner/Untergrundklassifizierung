import json
from src.untergrund import make_ctx, run_stages, Ctx
from src.untergrund.config import validate_config



def main() -> Ctx:
    with open("config.json", "r", encoding="utf-8") as f:
        cfg = json.load(f)

    validate_config(cfg)
   
    ctx = make_ctx(cfg)
    final_ctx = run_stages(ctx)
    return final_ctx


if __name__ == "__main__":
    test = main()
    print("\n+++ Test run complete +++\n")

    # Inhalt aller Ctx Attribute anzeigen
    for attr in test.__dataclass_fields__:
        value = getattr(test, attr)
        if isinstance(value, dict):
            print(f"{attr}: dict with (key,type(value)): {[(k, type(v)) for k, v in value.items()]}")
        else:
            print(f"{attr}: single Object of type {type(value)}")
   
        