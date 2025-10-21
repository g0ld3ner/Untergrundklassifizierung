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
    print(type(test.sensors))
    print(f"{len(test.sensors)} {test.sensors.keys()}")
    print("\n")
    for s, df in test.sensors.items():
        print(f"---{s}---")
        print(df.head(3))
        print(df.tail(3))
        print("\n")
    
    for s, df in test.sensors.items():
        print(f"---{s}---")
        print(df.info())
        print("\n")

    print("\nStart- und Endzeitpunkte der Sensoren:\n")
    for s, df in test.sensors.items():
        start = df.index[0]
        end = df.index[-1]
        print(f"{s:<20} Start: {start}  Ende: {end} Länge: {end - start}")
        