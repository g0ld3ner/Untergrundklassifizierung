# Decision Log - Untergrundklassifizierung

**Last Updated:** 2025-12-21
**Purpose:** Chronologischer Überblick aller wichtigen Projekt-Sessions & Entscheidungen

Dieses Dokument ist **append-only** - neue Sessions werden unten angefügt. Für technische Details siehe `specifications/`.

---

## 2025-09-27: Architektur-Review

**Entscheidungen:**
- Stage-Toggles: NEIN (alle Stages laufen immer, No-Op wenn nichts zu tun)
- Runner-Vertrag: `Ctx → Ctx`, Exception bei harten Fehlern
- UTC-Policy: Alles intern strikt in UTC
- Testing: pytest einführen, Schema-Kontrakte definieren
- Logging: Später (aktuell noch `print`)

**Outcome:**
→ ADR-001 (Stage-Toggles), ADR-002 (Runner-Vertrag), ADR-003 (UTC Zeit) erstellt
→ Architektur-Fundament gesetzt: Orchestrator → Stages → Runner → Pipelines → Pure Functions → Ctx

**Referenz:** `local/Protokoll_27_09_25.md`

---

## 2025-09-30: Roadmap + App + API Planning

**Entscheidungen:**
- Milestones M1-M6 definiert (Gerüst → Preprocessing → Features → Model → Export → Engineering)
- Streamlit App v0-v3 geplant (Upload & Sehen → Features → Klassifikation → Export)
- API-Scope festgelegt: v0 Read-Only, v1 Create-Run

**Outcome:**
→ Milestone_Matrix erstellt (M1-M6 + App v0-v3 + API v0-v1)
→ App bleibt "Thin UI" (keine Fachlogik, alles über Core-Services)
→ API als Adapter auf bestehende Services

**Referenz:** `local/Protokoll_30_09_25.md`, `local/Protokoll_30_09_25_2.md`

---

## 2025-10-04: M2 Preprocessing (Original Spec)

**Entscheidungen:**
- Preprocessing-Steps A1-E2 definiert: NaT-Handling, Sort, Dedupe, Resample, Impute, Filter
- UTC-Zeitindex `time_utc` als Pflicht
- Config-driven approach für alle Parameter
- Metriken in `ctx.artifacts["metrics"]` sammeln

**Outcome:**
→ M2 Preprocessing Spec erstellt
→ Später aktualisiert (siehe 2025-10-XX)

**Referenz:** `local/Protokoll_M2_Preprocessing_2025-10-04.md`

---

## 2025-10-XX: M2 Preprocessing (Aktualisiert)

**Änderungen:**
- Common Range Trim hinzugefügt (ersetzt Alignment)
  - Schneidet alle Sensoren auf gemeinsamen Überlappungsbereich
  - Essenziell für fensterbasierte Features & Cross-Sensor-Konsistenz
- Windowing als eigene Stage M2.5 geplant (zwischen PREPROCESS und FEATURES)
- `fn_kwargs` implementiert (parametrisierte Steps)
- Resampling mit `origin="epoch"` für deterministische Gitter

**Outcome:**
→ M2 Preprocessing Spec aktualisiert
→ M2.5 Windowing als neue Stage definiert
→ PREPROCESS liefert saubere, gleichmäßig getaktete Signale

**Referenz:** `local/Protokoll_M2_Preprocessing_2025-10_aktualisiert.md`, `local/protokoll_m_2_5_windowing_raw.md`

---

## 2025-11-17/18: M3 Feature Engineering (Phase 1 - Raw Features)

**Entscheidungen:**
- 3 Features für MVP: `acc_rms`, `acc_std`, `acc_p2p`
- Magnitude über x,y,z (orientierungsunabhängig)
- Geschwindigkeitsnormalisierung notwendig wegen v²-Abhängigkeit
- Montage-Position: Kein Problem für Single-Fahrt-Clustering
- Exponent-Strategie: MVP v0.1 = Config-basiert, MVP v0.2 = algorithmisch

**Outcome:**
→ Phase 1 implementiert: `acc_rms`, `acc_std`, `acc_p2p`
→ Smoke-Test erfolgreich (4 Windows mit plausiblen Werten)

**Referenz:** `local/Protokoll FeatureEngineering for MVP.md`, `specifications/M3_Features.md`

---

## 2025-11-23: M3 Feature Engineering (Phase 1 Complete + Phase 2)

**Entscheidungen:**
- Feature-Set erweitert auf 5 Features:
  - Amplitude: RMS, STD, P2P (v²-abhängig)
  - Frequenz: Zero-Crossing-Rate (v-abhängig)
  - Form: Kurtosis (v-unabhängig!) ✅
- P2P-Rolle: Primär Event-Detection, bleibt für Debugging/Interpretation
- GPS-Velocity: Direct from sensor (kein Haversine)
- **4-Faktor Confidence-Algorithmus** für `v_confidence` (0.0-1.0):
  1. speedAccuracy (~80% Gewicht)
  2. GPS-Punktanzahl (Robustheit-Penalty)
  3. Speed-Range Showstopper (0.3-20 m/s)
  4. Stabilität (Platzhalter für Post-MVP)

**Outcome:**
→ Phase 1: Alle 5 Raw Features implementiert ✅
→ Phase 2: `compute_window_velocity` implementiert mit Confidence ✅
→ Feature DataFrame hat 7 Spalten: v, v_confidence, acc_rms, acc_std, acc_p2p, zero_crossing_rate, acc_kurtosis

**Referenz:** `specifications/M3_Features.md`, `specifications/M3_Phase2_Velocity.md`

---

## 2025-11-26: M3 Feature Engineering (Phase 3 Complete)

**Entscheidungen:**
- Velocity Normalization implementiert: `*_vnorm` Spalten
- **Multiple Pipeline-Calls** mit verschiedenen Exponenten:
  - Amplitude-Features (RMS, STD, P2P): v^1.5
  - Frequenz-Feature (ZCR): v^1.0
  - Kurtosis: KEIN _vnorm (bereits v-unabhängig!)
- Config-Parameter: `velocity_epsilon`, `v_confidence_threshold`, `confidence_strategy`
- Hard threshold strategy mit Extensibility-Placeholders (soft_fallback, weighted)

**Outcome:**
→ Phase 3 komplett implementiert ✅
→ **ALLE 3 PHASEN FERTIG!**
→ Feature DataFrame hat 15 Spalten total (4 temporal + 2 velocity + 5 raw + 4 normalized)
→ 10 Unit Tests + 1 Integration Test geschrieben
→ **Ready for Model Stage (K-Means Clustering)**

**Referenz:** `specifications/M3_Features.md`

---

## 2025-12-20: Dokumentation Refactoring

**Entscheidungen:**
- `local/` → `doku/` Struktur definiert
- Decision_Log.md eingeführt (chronologisch, append-only)
- Hybrid-Ansatz: Decision Log (chronologisch) + thematische Specs (aktueller Stand)
- Duplikate konsolidiert (Context_extended → M3_Features.md, etc.)
- Pflege-Konventionen dokumentiert in `doku/README.md`
- Status-Header für alle Specs (Last Updated, Status, Related ADRs)

**Outcome:**
→ Saubere Doku-Struktur in `doku/` (Git-tracked)
→ `local/` bleibt bestehen für private Notizen
→ Roadmap vs. Specifications geklärt (WAS/WANN vs. WIE konkret)

**Referenz:** `doku/README.md`, Dieser Decision Log

---

## 2025-12-21: Dokumentations-Review & Abgleich mit Code

**Entscheidungen:**
- Stage-Namen vereinheitlicht: CLASSIFY → MODEL (konsistent mit stages.py)
- WINDOW-Stage in alle Dokumentationen aufgenommen (7 Stages total)
- ADR-004 Status: Planned → Accepted (Windowing implementiert)
- ADR-005 Update: ctx.windows → ctx.features["cluster"] (vereinfachte Architektur)
- ADR-007 Akzeptanzkriterien: Alle erfüllt und abgehakt
- Checkboxen in allen Specs aktualisiert (implementierte Items → [x])
- M3/M4 Beschreibungen: Features aktualisiert (RMS, STD, P2P, ZCR, Kurtosis), Model → K-Means

**Outcome:**
→ 11 Dokumentationsdateien überprüft und aktualisiert
→ Alle Status-Labels und Checkboxen mit Code-Realität synchronisiert
→ Offene Items identifiziert: Metrics-Tap (M2), Gap Detection (M2)
→ Dokumentation ist jetzt Single Source of Truth-konform

**Referenz:** Dieser Decision Log, `doku/` Ordner komplett

---

## 2025-12-21: M6 Reporting & Artifacts Planning

**Entscheidungen:**
- **Reporting-Architektur:** Spezifikation `M6_Artifacts_and_Reporting.md` erstellt.
- **Run-Identität:** `run_id` wird in `main.py` erzeugt und in `ctx.artifacts` abgelegt.
- **Ordner-Struktur:** Hierarchisch `artifacts/runs/{run_id}/{STAGE}/{step}/`.
- **Pipeline-API:** Neue Methode `pipeline.report()` erzwingt `dest="artifacts"`.
- **Reporter-Pattern:** `snapshot_reporter` erhält `stage` und `name` via `fn_kwargs` und baut Pfade selbst.
- **KISS:** Verzicht auf komplexe `partial`-Konstrukte oder Stage-Injection in die Pipeline-Klasse.

**Outcome:**
→ Spec `doku/specifications/M6_Artifacts_and_Reporting.md` finalisiert.
→ Implementierungsplan steht (main.py -> pipeline.py -> inspect.py).

**Referenz:** `doku/specifications/M6_Artifacts_and_Reporting.md`

---

## [Platzhalter für nächste Session]

**Template für neue Einträge:**
```markdown
## YYYY-MM-DD: [Thema der Session]

**Entscheidungen:**
- Entscheidung 1
- Entscheidung 2
- ...

**Outcome:**
→ Was wurde erstellt/geändert?
→ Nächster Schritt?

**Referenz:** `path/to/details.md`
```

---

**Wartung:** Bei neuen Sessions einfach oben anhängen (chronologisch absteigend). Alte Einträge nie ändern!
