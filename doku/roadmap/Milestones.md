# Milestone-Matrix – Untergrundklassifizierung

**Last Updated:** 2025-12-21

| Milestone | Kernaufgabe | Akzeptanzkriterien | Abhängigkeiten |
|-----------|-------------|--------------------|----------------|
| **M1 – Gerüst & Tests** | Pipeline-Verträge absichern, Routing- und Fehlerfälle testen, Config validieren | • Alle 11 Routing-Tests grün<br>• Fehlerfälle (None, falsche Signatur, fehlende Felder) werfen saubere Exceptions<br>• Config minimal validiert | Architektur steht (Ctx, Orchestrator, Runner) |
| **M2 – Preprocessing** | Robust machen: Zeitindex, Sort, Dedupe, Resample, Fill | • Alle Sensor-DFs haben `time_utc` als Index<br>• Lücken/Duplikate behandelt<br>• Metriken (`artifacts["metrics"]`) enthalten Rows, NA-Rate, Zeitspanne | M1 (Tests + Grundgerüst) |
| **M3 – Features (Set A)** | Erste berechnete Merkmale (RMS, STD, P2P, ZCR, Kurtosis) + Velocity-Normalisierung | • `ctx.features` enthält nur Input-Merkmale + Schlüsselspalten<br>• Unit-Tests mit Mini-Sensor-Daten stimmen mit Handrechnung überein | M2 (saubere Preprocessing-Daten) |
| **M4 – Classifier (MVP)** | K-Means Clustering pro Fahrt (unsupervised) | • `ctx.preds` gefüllt mit Labels pro Fenster<br>• deterministische Vorhersagen im Test | M3 (Features vorhanden) |
| **M5 – Export** | Artefakte persistieren (Features, Preds, Manifest) | • Export als Parquet/CSV<br>• Manifest mit `run_id`, Input-Hash, Config<br>• Test: Dateien korrekt, Schema konsistent | M3 (Features) + M4 (Preds) |
| **M6 – Engineering** | „Production-Hygiene“: Logging, Config, CLI, CI | • Logging ersetzt print<br>• Config via Pydantic validiert<br>• CLI-Entrypoint (`untergrund run ...`)<br>• CI-Pipeline mit pytest, Coverage, Linter | M1–M5 abgeschlossen |
| **App v0** | Frühe Demo ohne ML: Upload → Preprocess → Stats + Karte | • JSON-Upload → Ctx bis PREPROCESS<br>• Statistik-Panel (Metriken aus Core)<br>• Karte mit GPS + Metrik-Farbverlauf | M2 (Preprocess + Metrics) |
| **App v1** | Features im UI sichtbar | • Features aus FEATURES-Stage werden angezeigt<br>• Mapping Fenster → GPS-Position sichtbar | M3 (Features) |
| **App v2** | Klassifikation im UI | • Karten-Overlay mit Klassenfarben<br>• Diagnosefenster (Rohsignale + Features) | M4 (Classifier) |
| **App v3** | Export im UI | • Download-Buttons für Features, Preds, Manifest | M5 (Export) |
| **API v0** | Read-Only API für Artefakte | • Endpunkte `/runs/{id}/metrics|features|preds` liefern JSON<br>• Klare Fehlermeldungen<br>• `/api/v1` Versionierung | M1–M5 je nach Endpunkt |
| **API v1** | Runs erzeugen und abfragen | • POST `/runs` startet Pipeline mit Datei+Config<br>• GET `/runs/{id}` gibt Status/Infos zurück<br>• OpenAPI-Schema dokumentiert | API v0, Orchestrator stabil |
