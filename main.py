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
    print("\n--- Test run complete ---\n")
    print(type(test.sensors))
    print(test.sensors.keys())
    print(test.sensors["Location"])
    print(test.sensors["Location"].info())
    print(test.sensors["Accelerometer"].head())
    print(test.sensors["Accelerometer"].info())

