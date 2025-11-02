from dataclasses import dataclass, field
from typing import Any, Optional
import pandas as pd

@dataclass(frozen=True, slots=True)
class Ctx:
    """
    Context-Objekt für die MVP-Pipeline (eine Fahrt, lokale Klassifikation).

    Enthält nur die nötigsten Daten:
      - sensors:   Zeitreihen pro Sensor (kein "Metadata")
      - meta:      globale Fahrtinfos (aus "Metadata"-Sensor extrahiert)
      - features:  Fenster-Features (nur Input-Merkmale + Schlüsselspalten)
      - preds:     Vorhersagen/Labels je Fenster (gefüllt in LOCAL_CLASSIFY)
      - config:    Lauf-Parameter (z. B. Fenstergröße, Resample-Takt, Seeds)
      - artifacts: Provenienz (run_id, Pfade, Hashes), KEINE großen Objekte

    frozen=True  → unveränderlich, Änderungen nur über dataclasses.replace
    slots=True   → feste Attribute, weniger Speicher, keine "zufälligen" Felder
    """
    sensors: dict[str, pd.DataFrame] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)

    ##OLD:
    # features: Optional[pd.DataFrame] = None
    # preds: Optional[pd.Series] = None

    features: dict[str, pd.DataFrame] = field(default_factory=dict)
    preds: dict[str, pd.Series] = field(default_factory=dict)

    config: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, Any] = field(default_factory=dict)


def make_ctx(config: dict[str, Any]) -> Ctx:
    """
    Minimal factory for the MVP.
    No validation or normalization here — simply embeds the
    provided config dict into a fresh Ctx.
    """
    return Ctx(config=config)
