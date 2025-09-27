from enum import Enum, auto

class Stage(Enum):
    """Feste Stages. Reihenfolge wie deklaiert."""
    INGEST = auto()          # Einlesen, Sensor-Dict bauen, Metadata extrahieren
    SELECT = auto()          # gewünschte Sensoren filtern, fehlende melden
    PREPROCESS = auto()      # Zeitindex/UTC, Cleaning, Resample, etc.
    FEATURES = auto()        # Windowing (zuerst) + Feature-Berechnung
    CLASSIFY = auto()  # Klassifikation innerhalb der einen Fahrt (ML)
    EXPORT = auto()          # Artefakte persistieren (Features,,Preds, Config, etc.)