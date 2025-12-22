# GitHub Issues Seed – Untergrundklassifizierung

Dieses Dokument enthält grobgranulare Meilensteine als Vorschläge für GitHub-Issues.  
Es ist eine öffentliche Roadmap, kein strenger Vertrag – dient zur Orientierung, nicht zur Detailvorgabe.

---

### Issue: M1 – Gerüst & Tests
**Beschreibung:**  
Grundlage der Pipeline absichern. Fokus liegt auf Routing, Fehlerfälle und erste Testabdeckung.

**Akzeptanzkriterien:**  
- Orchestrator läuft alle Stages in fester Reihenfolge.  
- Routing- und Fehlerfall-Tests grün.  
- Config minimal validiert.  

---

### Issue: M2 – Preprocessing
**Beschreibung:**  
Preprocessing robuster machen: Zeitindex normalisieren, sortieren, Duplikate entfernen, Resample & Fill.

**Akzeptanzkriterien:**  
- Alle Sensor-DFs nutzen `time_utc` als Index.  
- Lücken und Duplikate behandelt.  
- Basis-Metriken (Rows, NA-Rate, Zeitspanne) im `artifacts["metrics"]` verfügbar.  

---

### Issue: M3 – Features (Set A)
**Beschreibung:**
Erste Feature-Berechnung implementieren (RMS, STD, P2P, ZCR, Kurtosis) + Velocity-Normalisierung.

**Akzeptanzkriterien:**  
- `ctx.features` gefüllt mit Merkmalen + Schlüsselspalten.  
- Tests mit Mini-Daten stimmen mit erwarteten Ergebnissen überein.  

---

### Issue: M4 – Classifier (MVP)
**Beschreibung:**
K-Means Clustering pro Fahrt implementieren, um erste Segment-Labels zu erzeugen (unsupervised).

**Akzeptanzkriterien:**  
- `ctx.preds` enthält Vorhersagen pro Fenster.  
- Modell liefert deterministische Ergebnisse auf Testdaten.  

---

### Issue: M5 – Export
**Beschreibung:**  
Artefakte persistieren, um spätere Analysen und Reproduzierbarkeit sicherzustellen.

**Akzeptanzkriterien:**  
- Export von Features und Preds als Parquet/CSV.  
- Manifest mit `run_id`, Input-Hash und Config erstellt.  

---

### Issue: M6 – Engineering-Ausbau
**Beschreibung:**  
Verbesserung der Software-Qualität und Nutzbarkeit.

**Akzeptanzkriterien:**  
- Logging statt Print-Ausgaben.  
- Config über Pydantic validiert.  
- CLI-Entrypoint (`untergrund run ...`) verfügbar.  
- CI-Pipeline (pytest, Linter, Coverage) eingerichtet.  

---

### Issue: App v0 – Upload & Karte
**Beschreibung:**  
Frühe Demo-App mit Streamlit. Nutzer lädt eine Fahrt hoch und sieht Statistik + Karte (ohne ML).

**Akzeptanzkriterien:**  
- Upload → Stages bis Preprocess laufen.  
- Statistik-Panel zeigt Metriken (Rows, NA-Rate, Zeitspanne).  
- Karte visualisiert Fahrt mit einfachem Farbverlauf.  

---

### Issue: App v1 – Features sichtbar
**Beschreibung:**  
Features aus der FEATURES-Stage in der App darstellen.

**Akzeptanzkriterien:**  
- Tabelle mit Feature-Werten.  
- Mapping Fenster → GPS-Position sichtbar.  

---

### Issue: App v2 – Klassifikation sichtbar
**Beschreibung:**  
Klassifikationsergebnisse in der Karte anzeigen.

**Akzeptanzkriterien:**  
- Segmente farbig nach Klasse.  
- Tooltip oder Diagnosefenster mit Features + Rohsignalen.  

---

### Issue: App v3 – Export in App
**Beschreibung:**  
Export-Funktion in der App anbieten.

**Akzeptanzkriterien:**  
- Download-Buttons für Features, Preds, Manifest.  

---

### Issue: API v0 – Read-Only Artefakte
**Beschreibung:**  
Erste API, die Ergebnisse der Pipeline lesbar macht.

**Akzeptanzkriterien:**  
- Endpunkte `/runs/{id}/metrics`, `/features`, `/preds` liefern JSON.  
- Fehlerfälle liefern saubere Fehlermeldungen.  
- Versionierung über `/api/v1/...`.  

---

### Issue: API v1 – Runs erzeugen
**Beschreibung:**  
API um neue Runs zu starten und deren Status abzufragen.

**Akzeptanzkriterien:**  
- POST `/runs` akzeptiert Datei + Config und startet Pipeline.  
- GET `/runs/{id}` liefert Status und Infos.  
- OpenAPI-Schema dokumentiert.  

---
