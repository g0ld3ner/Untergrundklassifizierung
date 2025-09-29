# Untergrundklassifizierung

Hier entsteht zukünftig ein Projekt zur Untergrundklassifizierung beim Radfahren.
Weitere Details folgen in Kürze.

##UPDATE:

### Aktueller Stand
- Grundgerüst der Pipeline steht: Stages (Ingest → Select → Preprocess → Features → Classify → Export) sind implementiert.
- Datenfluss läuft über ein zentrales, unveränderliches `Ctx`-Objekt.
- Erste Module (`ingest`, `select`) sind (minimalistisch) funktional, andere Stages aktuell noch Platzhalter.
- Konfiguration erfolgt über `config.json`.
- `pyproject.toml` + `pip install -e .` für sauberen Inport des Moduls "untergrund"
- Einführung von Pytest auf der CtxPipeline

### Nächste Schritte
- mehr Tests
- Ausbau von **Preprocessing** (Zeitindex, Resampling, Cleaning).
- Implementierung erster **Features** und simple Klassifizierung.
- **Export** von Ergebnissen und Artefakten.
- sauberes Logging einführen
- Visualisierung via Streamlit App


