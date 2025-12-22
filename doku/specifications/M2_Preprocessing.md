# M2 Specification: Preprocessing

**Last Updated:** 2025-12-21
**Status:** ✅ IMPLEMENTED
**Related ADRs:** ADR-003 (UTC Policy), ADR-005 (Immutability), ADR-007 (fn_kwargs)

*Aktualisierung und Konsolidierung des ursprünglichen M2-Fahrplans nach Integration von `fn_kwargs`, stabilem Resampling und Einführung des festen Common Range Trims.*

PREPROCESS ist funktional bis inkl. Resampling vorbereitet. Der Fokus liegt nun auf **Trim**, **Metrics**, **Validierungserweiterung**, **Config-/REQUIRE-Anpassungen** und **Windowing (Stage + Funktion)**.

---

## 1) Ausgangslage

- [x] Architektur: `Orchestrator → Stages → Runner → Pipelines → pure Functions → Ctx`.  
- [x] `fn_kwargs` implementiert (parametrisierte Schritte).  
- [x] Resampling-Design (IMU & Location) mit `origin="epoch"` definiert.  
- [x] Resampling-Parameter in **Config** & **_REQUIRE** final eingepflegt.  
- [x] PREPROCESS liefert nach Implementierung saubere, gleichmäßig getaktete Signale pro Sensor.  -> druch origin="epoch"
- [x] **Common Range Trim** implementiert und verankert (ersetzt Alignment).  
- [x] **Windowing** Als neue Stage + STAGE_FUNCS im Orchstrator + Runner (inkl. Funktionsplatzhalter hinzugefügt

---

## 2) Policies

- [x] **UTC strict:** alle Zeitachsen in UTC (`time_utc`).  
- [x] **No Toggles:** keine Schalter in der Pipeline.  
- [x] **Config-Driven:** Parameter aus Config (`fn_kwargs`).  
- [x] **Immutable Ctx:** pure Functions, kein Side-Effect.  
- [x] **Trim statt Alignment:** gemeinsamer Zeitbereich Pflicht.  
- [x] **Metrics:** alle Stages schreiben Kennzahlen in `ctx.artifacts["metrics"]`.

---

## 3) Schritte (WHAT / WHY / HOW)

### A) Index & Schema (Basis)
- [x] `time_to_index` – konvertiert ns-Zeitstempel zu UTC-DatetimeIndex.  
- [x] `handle_nat_in_index` – entfernt NaT-Lücken.  
- [x] `sort_sensors_by_time_index` – sortiert stabil.  
- [x] `group_duplicate_timeindex` – aggregiert Duplikate.  
- [x] **`validate_basic_preprocessing`** implementiert: prüft
  - [x] DatetimeIndex vorhanden
  - [x] UTC-Timezone
  - [x] Monoton steigend
  - [x] Keine Duplikate
  - [x] Keine NaT-Werte
  - [ ] Resampling-Ergebnis (gleichmäßige Δt je Sensor) – *optional für Zukunft*
  - [ ] Trim-Konsistenz (alle Sensoren teilen denselben Zeitbereich) – *optional für Zukunft*

---

### B) Resampling & Zeitbereich

#### B1 – Config-Driven Resampling
- [x] **WHAT:** Zielraten & Aggregations-/Interpolationsregeln pro Sensor in **Config** verankern; **_REQUIRE** aktualisieren.  
- [x] **WHY:** Reproduzierbarkeit und Nachvollziehbarkeit.  
- [x] **HOW:** `resample_*` liest Parameter aus `ctx.config["resample"]`; Keys/Typen in `_OPTIONAL` festgehalten.

#### B2 – Gap Detection & Coverage Metrics
- [ ] **WHAT:** Lückenanalyse und Messdichte-Bewertung.  
- [ ] **WHY:** Frühe Transparenz über Datenqualität.  
- [ ] **HOW:** Berechnet `orig_rate_hz_est`, `target_rate_hz`, `n_gaps`, `max_gap_s`, `coverage_pct`; speichert Ergebnisse in `ctx.artifacts["metrics"]`.  
  (Keine Imputation – M2 bleibt read-only.)

#### B3 – Common Range Trim (ersetzt Alignment)
- [x] **WHAT:** Schneidet alle Sensoren auf den gemeinsamen Überlappungsbereich (`t_start = max(min_i)`, `t_end = min(max_i)`).  
- [x] **WHY:** Alle Sensoren decken denselben gültigen Zeitbereich ab – essenziell für fensterbasierte Features & Cross-Sensor-Konsistenz.  
- [x] **HOW:** Fester Pipeline-Step am Ende von PREPROCESS; bei fehlender Überlappung Exception mit min/max-Angabe.


#### B4 – Advanced Preprocessing
- [ ] **WHAT:** Restlichen für die Klassifizierung benötigten Preprocess-Funktionen implementieren (Filter, etc. ...)
- [ ] **WHY:** MVP lauffähig bekommen
- [ ] **HOW:** Liste der zu implementierednen Funktionen: ...?

---

### C) Windowing (Stage + Funktion)
- [x] **PREWORK** Neue Stage zwischen PREPROCESS und FEATURES
- [x] **WHAT:** Windowing definiert Zeitfenster und stellt eine Windowing-Funktion bereit
- [x] **WHY:** Trennung zwischen Signalbereinigung (PREPROCESS) und Analyse-Raster (WINDOWING)
- [x] **HOW:** `run_window()` + `windowing()` erzeugen Fenster-DF (`start_utc`, `end_utc`, `center_utc`) in `ctx.features["cluster"]`; Parameter (`duration_s`, `hop_s`) aus Config

---

### D) Metrics Tap
- [ ] **WHAT:** Erfasst pro Sensor Kennzahlen (Zeilen, Na-Rate, Duplikate, Gaps, Coverage).  
- [ ] **WHY:** Früher Überblick über Signalqualität (read-only).  
- [ ] **HOW:** Tap-Step am Ende von PREPROCESS; schreibt in `ctx.artifacts["metrics"]`.

---

## 4) Config-Aufgaben (konkret)

- [x] **Config erweitern**: `preprocess.resample.{imu,location}.(target_rate_hz, agg/interp bzw. fill/limit)`  
- [x] **_REQUIRE aktualisieren**: obligatorische/optionale Keys & Typen für Resample + Windowing (`duration_s`, `hop_s`).  
- [x] **validate_config**: strukturelle/typbasierte Prüfung (keine harte Semantik) für neue Keys.  
- [x] **Docs**: README/Protokoll-Abschnitte zur Config aktualisieren.

---


## 6) Definition of Done (M2)

- [x] PREPROCESS enthält alle Basis-Steps inkl. **Common Range Trim**
- [x] `validate_basic_preprocessing` prüft UTC, Monotonie, Duplikate, NaT
- [x] **Config** ist für Resampling + Windowing aktualisiert
- [ ] Metrics vollständig pro Sensor (Rates, Gaps, Coverage) – *noch offen*
- [x] **Windowing-Stage & -Funktion** erzeugen Fenster-DF in `ctx.features`
- [x] Tests grün für Resample, Trim, Validation, Windowing (78 Tests gesamt)
- [x] Pipeline deterministisch und reproduzierbar (keine Toggles)

---

## 7) Offene Punkte / Next Steps

- [ ] Umfang & Struktur der Metrics (Tabellenformat oder Dict).  
- [ ] Endgültiges Schema für `windows`.  
- [ ] Zeitpunkt für Imputation (nach M2 oder erst M3).  
- [ ] Einbindung von Metrics in Export/Manifest.

---

## 8) Kurz-Resümee

Das neue M2-Design ersetzt zeitliches Alignment durch den festen **Common Range Trim**.  
Resampling, Validation, Trim und die **Windowing-Stage mit Funktion** bilden die stabile Grundlage für die Feature-Bildung.  
Die PREPROCESS-Stage ist damit konzeptionell abgeschlossen, sobald die oben markierten TODOs umgesetzt sind.
