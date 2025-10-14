from typing import Any

#Pflichtfelder in der Config-Datei
_REQUIRED = {
    "input_path": str,
    "sensor_list": list,
}

_OPTIONAL = {
    "resample_imu": dict,
    "resample_location": dict,
}

def validate_config(cfg: dict[str, Any]) -> dict[str, Any]:
    '''
    Validiert die Konfigurationsdatei.
    Prüft ob alle erforderlichen Felder vorhanden sind.
    Erforderliche und optionale Felder werden auf den richtigen Typ geprüft.
    '''
    # ist cfg ein dict?
    if not isinstance(cfg, dict):
        raise ValueError("Config must be a dict")

    req_checked = set() #überprüfte Felder
    # stimmt der Typ der Pflichtfelder?
    for key, expected_type in _REQUIRED.items():
        if key not in cfg:
            raise ValueError(f"Missing required config key: {key}")
        if not isinstance(cfg[key], expected_type):
            raise ValueError(
                f"Wrong type for required '{key}': expected {expected_type.__name__}, "
                f"got {type(cfg[key]).__name__}"
            )
        req_checked.add(key)

    opt_checked = set()
    # stimmt der Typ der optionalen Felder?
    for key, expected_type in _OPTIONAL.items():
        if key in cfg:
            if not isinstance(cfg[key], expected_type):
                raise ValueError(
                    f"Wrong type for optional '{key}': expected {expected_type.__name__}, "
                    f"got {type(cfg[key]).__name__}"
                )
            opt_checked.add(key)

    # nicht überprüfte Felder melden
    unchecked = sorted(set(cfg.keys()) - req_checked - opt_checked)
    if unchecked:
        print(f"[validate_config] Unchecked config keys: {unchecked}")

    return cfg