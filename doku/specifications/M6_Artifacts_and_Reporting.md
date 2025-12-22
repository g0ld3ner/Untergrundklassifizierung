# M6 Specification: Artifacts & Reporting Architecture

**Last Updated:** 2025-12-21
**Status:** 🟡 PLANNING
**Related:** ADR-003 (Persistence), ADR-006 (Roles)

Dieses Dokument spezifiziert die Architektur für das Speichern von Zwischenergebnissen (Snapshots), Metriken und Reports. Ziel ist volle Reproduzierbarkeit und Debugging-Fähigkeit ohne "Wegwerf-Skripte".

---

## 1. Run Identity (`run_id`)

Damit Artefakte verschiedener Durchläufe nicht kollidieren, benötigt jeder Pipeline-Run eine eindeutige Identität.

**Konzept:**
- Die `run_id` wird **ganz am Anfang** in `main.py` generiert.
- Format: `YYYY-MM-DD_HH-MM_{hash}` (z. B. `2025-12-21_16-30_a1b2c`).
- Sie wird im `Ctx` unter `ctx.artifacts["run_id"]` abgelegt.
- Alle Reporter lesen diese ID, um ihre Zielpfade zu bauen.

---

## 2. Ordner-Struktur (Physisch)

Wir vermeiden flache Ordner ("Datei-Chaos"). Stattdessen erzwingen wir eine Hierarchie, die der Pipeline-Struktur folgt.

```text
artifacts/
  └── runs/
      └── {run_id}/                  <-- Container für diesen Lauf
          ├── config.json            <-- Die verwendete Config (Snapshot)
          ├── manifest.json          <-- Index aller erzeugten Dateien
          ├── 01_INGEST/             <-- Ordner pro Stage (Upper Case)
          ├── 03_PREPROCESS/
          │   ├── after_filter/      <-- Ordner pro Step/Reporter
          │   │   ├── Acc.parquet
          │   │   └── Gyro.parquet
          │   └── data_quality.json
          └── 99_EXPORT/
```

---

## 3. Die API-Erweiterung: `pipeline.report()`

Um ADR-006 ("Reporter schreiben nach artifacts") technisch durchzusetzen, wird `CtxPipeline` um eine Methode erweitert.

**Methode:** `report(fn, *, source, name, fn_kwargs)`

**Verhalten:**
1.  Sie ist ein Wrapper um `.add()`.
2.  Sie fügt automatisch `"artifacts"` zur `source`-Liste hinzu.
3.  Sie setzt **erzwungen** `dest="artifacts"`.
4.  Dies garantiert, dass Reporter *nur* das Logbuch fortschreiben können und keine Sensordaten verändern.

**Interne Umsetzung (Konzept):**
```python
def report(self, fn, *, source, name=None, fn_kwargs=None):
    # Automatisch 'artifacts' als Input und Output erzwingen
    real_source = [*source, "artifacts"] if isinstance(source, list) else [source, "artifacts"]
    
    return self.add(
        fn, 
        source=real_source, 
        dest="artifacts",  # <--- Hardcoded Safety
        name=name, 
        fn_kwargs=fn_kwargs
    )
```

**Aufruf im Runner:**
```python
pipeline.report(
    snapshot_reporter,
    source="sensors",           # Wir geben nur an, WAS wir reporten wollen
    fn_kwargs={
        "stage": "PREPROCESS",  # Kontext für den Pfad
        "name": "after_filter"
    }
)
```

---

## 4. Der Snapshot-Reporter (Design)

Eine generische Funktion in `src/untergrund/shared/inspect.py`, die beliebige Teile des Contexts (Sensoren, Features) als Parquet oder JSON sichert.

**Signatur:**
```python
def snapshot_reporter(data: Any, artifacts: dict, *, stage: str, name: str, ...) -> dict:
    ...
```

**Funktionsweise:**
1.  Liest `run_id` aus dem übergebenen `artifacts`-Dict.
2.  Baut Pfad: `artifacts/runs/{run_id}/{stage}/{name}`.
3.  Filtert Daten (optional via `include_keys` / `exclude_keys`).
4.  Speichert DataFrames als `.parquet`, Dicts als `.json`.
5.  **Wichtig:** Fügt einen Eintrag in `artifacts["snapshots"]` hinzu (für das Manifest).
6.  Gibt das aktualisierte `artifacts`-Dict zurück.

---

## 5. Integration in Streamlit (Ausblick)

Da die Daten strukturiert und selbsterklärend (Manifest) abgelegt sind, kann eine Streamlit-App später einfach auf den Ordner `artifacts/runs/` zugreifen.

- User wählt Run-ID aus Dropdown.
- App liest `manifest.json`.
- App bietet verfügbare Snapshots zur Visualisierung an.

Dies entkoppelt die Pipeline (Schreiben) vollständig von der Analyse (Lesen).