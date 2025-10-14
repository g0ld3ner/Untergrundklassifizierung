from enum import Enum, auto

class Stage(Enum):
    """Feste Stages. Reihenfolge wie deklaiert."""
    INGEST = auto()          # Einlesen, Sensor-Dict bauen, Metadata extrahieren
    SELECT = auto()          # gewünschte Sensoren filtern, fehlende melden
    PREPROCESS = auto()      # Zeitindex/UTC, Cleaning, Resample, etc.
    WINDOW = auto()      # Zeitfenster als DataFrame
    FEATURES = auto()        # Feature-Berechnung und Zusammenführung in das DataFrame aus Windowing
    CLASSIFY = auto()  # Klassifikation innerhalb der einen Fahrt (ML)
    EXPORT = auto()          # Artefakte persistieren (Features, Preds, Config, etc.)