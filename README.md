# Untergrundklassifizierung

Hier entsteht ein Projekt zur Auswertung aufgezeichneter Fahrraddaten.
Ziel ist es, aus den Sensordaten einer Fahrt Rückschlüsse auf den befahrenen Untergrund zu ziehen.

#### Designprinzip:
_Das Projekt setzt auf explizite, manuell komponierte Pipelines._
_Jede Stage ist eine offene Sequenz aus reinen Funktionen mit klaren Verträgen (Ctx → Ctx)._
_Es gibt keine verpflichtenden Standard-Steps. Keine Config-Toggles_
_Presets dienen Gruppierung zwecks Vereinfachung des Pipeline baus, nicht der Einschränkung._
_Ziel ist maximale Experimentierbarkeit bei gleichzeitiger Robustheit und Reproduzierbarkeit._

Weitere Details folgen in Kürze.

##UPDATE:

### Aktueller Stand
- Grundgerüst der Pipeline steht: Stages (Ingest → Select → Preprocess → Windown → Features → Classify → Export) sind implementiert.
- Datenfluss läuft über ein zentrales, unveränderliches `Ctx`-Objekt.
- Erste Module (`ingest`, `select`) sind (minimalistisch) funktional, Basic Preprocessing abgeschlossen, andere Stages aktuell noch Platzhalter.
- Konfiguration erfolgt über `config.json`.
- `pyproject.toml` + `pip install -e .` für sauberen Inport des Moduls "untergrund"
- Einführung von Pytest auf der CtxPipeline, Senor-Dekoratoren und einigen Preprocessing Funktionen

### Nächste Schritte
- Ausbau von **Preprocessing** (Filter, etc.).
- Implementierung erster **Features** und simple **Klassifizierung**.
- **Export** von Ergebnissen und Artefakten.
- sauberes Logging einführen
- Visualisierung via Streamlit App
- Presets für die Runner ermöglichen
- mehr Testing


