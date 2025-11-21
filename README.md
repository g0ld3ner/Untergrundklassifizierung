# Untergrundklassifizierung

Hier entsteht ein Projekt zur Auswertung aufgezeichneter Fahrraddaten.
Ziel ist es, aus den Sensordaten einer Fahrt Rückschlüsse auf den befahrenen Untergrund zu ziehen.

#### MVP Ziel:
 - Fahrten per SensorLogger App aufnehmen
 - Ingest -> Select -> Preprocessing → Windowing → Features → Model → Export
 - Wenige grundlegende Features berechnen (RMS, STD, ZCR, etc.)
 - Untergründe in **Cluster** unterteilen (K-Means?)
 - Visulisierung der Features sowie der Predcitions auf einer Karte

#### Designprinzip:
_Das Projekt setzt auf explizite, manuell komponierte Pipelines._

_Jede Stage ist eine offene Sequenz aus reinen Funktionen mit klaren Verträgen (Ctx → Ctx)._

_Es gibt keine verpflichtenden Standard-Steps. Keine Config-Toggles_

_Presets dienen Gruppierung zwecks Vereinfachung des Pipeline baus, nicht der Einschränkung.(Presets werden erst später implementiert)_

_Ziel ist maximale Experimentierbarkeit bei gleichzeitiger Robustheit und Reproduzierbarkeit._


### UPDATE:

#### Aktueller Stand
- Grundgerüst der Pipeline steht: Stages (Ingest → Select → Preprocess → Windown → Features → Model → Export) sind implementiert.
- Datenfluss läuft über ein zentrales, unveränderliches `Ctx`-Objekt.
- Erste Module (`ingest`, `select`) sind funktional
- Preprocessing abgeschlossen
- Features für das MVP-Clustering implementiert -> Features müssen noch in Abhängigkeit zur Geschwindigkeit gebracht werden. 
- Konfiguration erfolgt über `config.json`.
- `pyproject.toml` + `pip install -e .` für sauberen Inport des Moduls "untergrund"
- Einführung von Pytest auf der CtxPipeline, Senor-Dekoratoren und einigen Preprocessing Funktionen sowie Features

#### Nächste Schritte
- Features entsprechend als v-abhängige Variante berechen.
- Implementierung des Models (Clustering mit K-means).
- **Export** von Ergebnissen und Artefakten.
- Visualisierung via Streamlit App
- sauberes Logging einführen
- Detailiertere Dokumentation und Anleitung zu Installation/Nutzung
- Presets für die Runner ermöglichen
- CLI bzw. API ...
- mehr Testing



