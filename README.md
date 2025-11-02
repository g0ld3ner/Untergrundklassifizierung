# Untergrundklassifizierung

Hier entsteht ein Projekt zur Auswertung aufgezeichneter Fahrraddaten.
Ziel ist es, aus den Sensordaten einer Fahrt Rückschlüsse auf den befahrenen Untergrund zu ziehen.

#### MVP Ziel:
 - Fahrten per SensorLogger App aufnehmen
 - Sauberer Ingest -> Select -> Preprocessing
 - Wenige grundlegende Features berechnen (RMS, etc.)
 - Untergründe in Cluster unterteilen (K-Means?)
 - Export 
 - Visulisierung auf Karte

#### Designprinzip:
_Das Projekt setzt auf explizite, manuell komponierte Pipelines._
_Jede Stage ist eine offene Sequenz aus reinen Funktionen mit klaren Verträgen (Ctx → Ctx)._
_Es gibt keine verpflichtenden Standard-Steps. Keine Config-Toggles_
_Presets dienen Gruppierung zwecks Vereinfachung des Pipeline baus, nicht der Einschränkung._
_Ziel ist maximale Experimentierbarkeit bei gleichzeitiger Robustheit und Reproduzierbarkeit._


##UPDATE:

### Aktueller Stand
- Grundgerüst der Pipeline steht: Stages (Ingest → Select → Preprocess → Windown → Features → Model → Export) sind implementiert.
- Datenfluss läuft über ein zentrales, unveränderliches `Ctx`-Objekt.
- Erste Module (`ingest`, `select`) sind (minimalistisch) funktional, Basic Preprocessing abgeschlossen, andere Stages aktuell noch Platzhalter.
- Konfiguration erfolgt über `config.json`.
- `pyproject.toml` + `pip install -e .` für sauberen Inport des Moduls "untergrund"
- Einführung von Pytest auf der CtxPipeline, Senor-Dekoratoren und einigen Preprocessing Funktionen
- Ausbau von **Preprocessing** (Filter, AntiAliasing, etc.)

### Nächste Schritte
- Implementierung erster **Features** und simples **Clustering**.
- **Export** von Ergebnissen und Artefakten.
- sauberes Logging einführen
- Visualisierung via Streamlit App
- Presets für die Runner ermöglichen
- CLI bzw. API ...
- mehr Testing


