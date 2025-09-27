from typing import Any

#Pflichtfelder in der Config-Datei
_REQUIRED = {
    "input_path": str,
    "sensor_list": list,
}

def validate_config(cfg: dict[str, Any]) -> dict[str, Any]:
    '''
    Validiert die Konfigurationsdatei. Prüft auf erforderliche Felder und deren Typen.
    '''
    # ist cfg ein dict?
    if not isinstance(cfg, dict):
        raise ValueError("Config must be a dict")

    checked = set() #überprüfte Felder
    # stimmt der Typ der Pflichtfelder?
    for key, expected_type in _REQUIRED.items():
        if key not in cfg:
            raise ValueError(f"Missing config key: {key}")
        if not isinstance(cfg[key], expected_type):
            raise ValueError(
                f"Wrong type for '{key}': expected {expected_type.__name__}, "
                f"got {type(cfg[key]).__name__}"
            )
        checked.add(key)

    # nicht überprüfte Felder melden
    unchecked = sorted(set(cfg.keys()) - checked)
    if unchecked:
        print(f"[validate_config] Unchecked config keys: {unchecked}")

    return cfg