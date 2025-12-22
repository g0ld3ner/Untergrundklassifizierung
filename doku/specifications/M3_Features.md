# M3 Specification: Feature Engineering

**Last Updated:** 2025-12-21
**Status:** ✅ IMPLEMENTED
**Related ADRs:** ADR-007 (Parametrizable Steps), ADR-009 (Config Prelayer)

## PROJECT CONTEXT
- **Projekt:** Untergrundklassifizierung aus Fahrrad-Sensordaten (Smartphone)
- **Ziel:** K-Means Clustering pro Fahrt (Single-Fahrt-Clustering)
- **Stage:** Feature Engineering (M3 – FEATURES)
- **Status:** ✅ **ALLE 3 PHASEN KOMPLETT!** (Phase 1: Raw Features, Phase 2: Velocity, Phase 3: Normalization)

## KEY DECISIONS FROM SESSION

### 1) FINAL MVP Feature Strategy - ✅ KOMPLETT IMPLEMENTIERT!

**Phase 1: Raw Features (Time-Domain, Accelerometer) - ✅ DONE (2025-11-23):**
- `acc_rms` ✅ (Magnitude RMS over x, y, z)
- `acc_std` ✅ (Standard deviation over all axes)
- `acc_p2p` ✅ (Peak-to-peak: max - min)
- `zero_crossing_rate` ✅ (Frequency-proxy, Vorzeichenwechsel)
- `acc_kurtosis` ✅ (Excess Kurtosis, Verteilungsform)

**Phase 2: Velocity Extraction - ✅ DONE (2025-11-23):**
- `compute_window_velocity` ✅ → Spalten `v` (m/s) + `v_confidence` (0.0-1.0)
- **4-Faktor Confidence-Algorithmus** (speedAccuracy, GPS-Punktanzahl, Range-Limits, Stabilität-Placeholder)

**Phase 3: Velocity Normalization - ✅ DONE (2025-11-26):**
- `normalize_features_by_velocity` ✅ → `*_vnorm` Spalten
- **2 Pipeline-Calls** mit verschiedenen Exponenten (v^1.5 für Amplitude, v^1.0 für Frequenz)
- Hard threshold strategy mit Extensibility-Placeholders (soft_fallback, weighted)

---

## CRITICAL INSIGHTS FROM DISCUSSION

### 2) Feature Roles & Dimensions

| Feature | Dimension | v-abhängig? | Primäre Rolle | Sekundäre Rolle |
|---------|-----------|-------------|---------------|-----------------|
| `acc_rms` | Amplitude | Ja (v²) | Untergrund-Stärke | Gesamtenergie |
| `acc_std` | Amplitude | Ja (v²) | Variabilität | Streuung |
| `acc_p2p` | Amplitude | Ja (v²) | **Event-Detection** | **Debugging/Anomalie** ✅ |
| `zero_crossing_rate` | Frequenz | Ja (v) | Frequenz-Charakteristik | "Wie schnell?" |
| `acc_kurtosis` | Form | **Nein ✅** | **Regelmäßigkeit** | **v-unabhängig!** |

**KEY INSIGHT: Feature Diversity!**
- Amplitude × 3 (RMS, STD, P2P)
- Frequenz × 1 (ZCR)
- Form × 1 (Kurtosis) ← **einzigartig: v-unabhängig!**

---

### 3) Why Keep P2P (Even Though It's Event-Detection)?

**Original concern:** P2P misst einzelne Extremwerte (Schlaglöcher), nicht typische Oberflächeneigenschaften

**Decision: KEEP IT!**

**Reasons:**
✅ Already implemented (sunk cost = zero)  
✅ Valuable for **debugging/interpretation**:
   - "Warum ist RMS in diesem Fenster so hoch?" → P2P zeigt: Einzelnes Schlagloch!
   - "Ist das eine raue Oberfläche oder ein Event?" → P2P vs. Kurtosis unterscheidet das!
✅ Doesn't hurt (only 5 features total, no overfitting risk)  
✅ Model doesn't have to use it (K-Means will weight it appropriately)  
✅ "Features die man hat, hat man" – Engineering principle: Keep options open  

**Use cases:**
- Quality control: Unrealistisch hohe P2P → Sensor artifacts?
- Cluster interpretation: "Warum ist Cluster 3 anders?" → P2P zeigt Events
- Outlier analysis: P2P hoch + Kurtosis hoch = Einzelevents, nicht Oberfläche

---

### 4) Kurtosis – THE Feature for "Regelmäßig vs. Chaotisch"

**What it measures:**
- **NOT** "wie stark" (that's RMS)
- **NOT** "normierte Amplitudenstärke"
- **Form der Verteilung:** Wie häufig gibt es Extremwerte?

**Formula (Excess Kurtosis, scipy default):**
```python
from scipy.stats import kurtosis
kurt = kurtosis(signal, fisher=True)  # Excess: Normalverteilung = 0
```

**Interpretation:**
- **< 0:** Flache Verteilung (gleichmäßig rau, z.B. feiner Schotter)
- **≈ 0:** Normalverteilung (typische Straße)
- **0–3:** Leicht erhöht (gelegentliche Peaks, z.B. Kopfstein)
- **3–10:** Stark erhöht (häufige Extremwerte, z.B. Schlaglöcher)
- **> 10:** Sehr stark (viele krasse Stöße, z.B. Offroad)

**Why velocity-independent:**
- Normierung durch σ (Standardabweichung)
- Bei höherer v: σ steigt, aber **Form bleibt gleich**
- Kurtosis misst **relative Verteilung**, nicht absolute Amplitude

**Physical intuition (CRITICAL):**
```
Scenario A: Gleichmäßiger Schotter
Signal: [3.0, 3.2, 2.8, 3.1, 2.9, ...]
RMS = 3.0, Kurtosis ≈ 0 (gleichmäßig)

Scenario B: Asphalt + Schlaglöcher
Signal: [0.5, 0.6, 12.0, 0.5, 0.6, 11.5, ...]
RMS ≈ 3.0 (ähnlich!), Kurtosis ≈ 8 (chaotisch!)

→ Kurtosis trennt diese, RMS kann es nicht!
```

**Why Kurtosis is THE feature:**
✅ DAS Feature für "regelmäßig rau" vs. "unregelmäßig (Löcher/Kanten)"  
✅ Unterscheidet Kopfstein (gleichmäßig) von Asphalt+Schlaglöcher (Events)  
✅ Geschwindigkeitsunabhängig (einziges Feature!)  
✅ Komplementär zu allen anderen Features  

---

### 5) STD vs. Kurtosis – Are They Redundant?

**Short answer: NO, but related.**

**Mathematical difference:**
- STD: `mean((x - μ)²)` → alle Abweichungen gleich gewichtet
- Kurtosis: `mean(((x - μ) / σ)⁴)` → **Extremwerte 10.000× stärker gewichtet!**

**Example showing difference:**
```
Signal A (gleichmäßig): [3, 4, 2, 5, 3, 4, 2, 5]
STD = 1.12, Kurtosis = -0.8 (flach)

Signal B (Events): [0, 0, 0, 15, 0, 0, 0, 0]
STD = 4.5, Kurtosis = 7.0 (extrem!)

Signal C (gleichmäßig verteilt): [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
STD = 2.87, Kurtosis = -1.2 (flach)

→ STD kann B und C nicht trennen (beide haben hohe STD)
→ Kurtosis trennt perfekt (7.0 vs. -1.2)
```

**Correlation:**
- Typisch: 0.4–0.7 (moderat, nicht perfekt)
- Beide bringen eigene Information
- STD = v-abhängig (Gesamtvariabilität)
- Kurtosis = v-unabhängig (Extremwert-Häufigkeit)

**Keep both!**

---

## CURRENT IMPLEMENTATION STATUS - ✅ ALL PHASES COMPLETE!

### Existing Code (✅ ALL DONE)
- `src/untergrund/runners/features.py`:
  - `run_features()`: Pipeline runner ✅
  - Phase 1 Features (Raw): ✅
    - `acc_rms()`: ✅ Implemented
    - `acc_std()`: ✅ Implemented
    - `acc_p2p()`: ✅ Implemented
    - `zero_crossing_rate()`: ✅ Implemented
    - `acc_kurtosis()`: ✅ Implemented
  - Phase 2 (Velocity): ✅
    - `compute_window_velocity()`: ✅ Implemented
  - Phase 3 (Normalization): ✅
    - `normalize_features_by_velocity()`: ✅ Implemented

### Actual Feature DataFrame Structure (15 columns)
**After Phase 3 implementation:**
```
| window_id | start_utc | end_utc | center_utc |  ← Temporal (4)
| v | v_confidence |                            ← Velocity (2)
| acc_rms | acc_std | acc_p2p | zero_crossing_rate | acc_kurtosis |  ← Raw Features (5)
| acc_rms_vnorm | acc_std_vnorm | acc_p2p_vnorm | zero_crossing_rate_vnorm |  ← Normalized (4)
```
**Note:** `acc_kurtosis` has NO `_vnorm` column (already velocity-independent)

---

## NEXT STEPS (PRIORITIZED) - UPDATED 2025-11-26

### ✅ COMPLETED - All Feature Engineering Phases Done!

**Phase 1 (Raw Features) - ✅ DONE (2025-11-23):**
- ✅ `acc_rms`, `acc_std`, `acc_p2p`, `zero_crossing_rate`, `acc_kurtosis` all implemented
- ✅ Tests written and passing
- ✅ Integration with pipeline complete

**Phase 2 (Velocity Extraction) - ✅ DONE (2025-11-23):**
- ✅ `compute_window_velocity` implemented with 4-factor confidence algorithm
- ✅ Columns `v` (m/s) and `v_confidence` (0.0-1.0) added to features
- ✅ Tests written (10 unit + 1 integration)

**Phase 3 (Velocity Normalization) - ✅ DONE (2025-11-26):**
- ✅ Config section `velocity_normalization` added to `config.json`
- ✅ `normalize_features_by_velocity` implemented (133 lines)
- ✅ Multiple pipeline calls pattern (v^1.5 for amplitude, v^1.0 for frequency)
- ✅ Hard threshold strategy with extensibility placeholders
- ✅ 10 unit tests + 1 integration test written

---

### 🎯 ACTUAL NEXT STEP: Model Stage (K-Means Clustering)

**Goal:** Implement unsupervised clustering on the 15 feature columns

**Tasks:**
1. Implement `run_model()` in `src/untergrund/runners/model.py`
2. Feature selection/scaling (StandardScaler on relevant columns)
3. K-Means clustering (k=4 as starting point)
4. Add cluster labels to `ctx.preds`
5. Initial evaluation (Silhouette Score)
6. Tests for clustering pipeline

**Blocking:** None - all features ready!

---

## TECHNICAL NOTES

### Zero-Crossing-Rate Details:
```python
# Example:
signal = [1, 2, -1, -2, 1, 3, -1]
sign = [1, 1, -1, -1, 1, 1, -1]
diff(sign) = [0, -2, 0, 2, 0, -2]  # non-zero = sign change
sign_changes = 3
zcr = 3 / 7 = 0.43
```

**Physical meaning:**
- Kopfstein: viele kleine Stöße → hohe ZCR
- Asphalt: wenig Schwingung → niedrige ZCR
- Schlagloch: ein großer Stoß → niedrige ZCR (aber hohe P2P!)

### Kurtosis Details:
```python
# scipy.stats.kurtosis defaults:
# - fisher=True: Excess kurtosis (Normalverteilung = 0)
# - fisher=False: Standard kurtosis (Normalverteilung = 3)
# → Use Excess (fisher=True) for easier interpretation!

# Why x⁴?
# Small deviation: (0.1)⁴ = 0.0001 (negligible)
# Large deviation: (10)⁴ = 10000 (dominates!)
# → Extremwerte werden extrem stark gewichtet
```

### Haversine Formula (for later, Phase 2):
```python
from math import radians, cos, sin, asin, sqrt

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000  # Earth radius in meters
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    
    a = sin(dphi/2)**2 + cos(phi1) * cos(phi2) * sin(dlambda/2)**2
    c = 2 * asin(sqrt(a))
    
    return R * c  # Distance in meters
```

---

## TESTING STRATEGY

### Unit Tests (per feature):
```python
def test_zero_crossing_rate_basic():
    # Signal: [1, -1, 1, -1, 1]
    # Expected ZCR: 4 / 5 = 0.8
    pass

def test_acc_kurtosis_normal_distribution():
    # Normal distributed signal
    # Expected: Kurtosis ≈ 0 (Excess)
    pass

def test_acc_kurtosis_single_spike():
    # Signal: [0, 0, 0, 10, 0, 0]
    # Expected: Kurtosis > 5 (high)
    pass
```

### Integration Test:
```python
def test_full_feature_pipeline_5_features():
    # Real data (1 ride, ~10 windows)
    # Check: 5 feature columns present
    # Check: No unexpected NaNs
    # Check: Plausible values (ZCR > 0, Kurtosis reasonable)
    pass
```

---

## IMPORTANT CONSTRAINTS

### From ADRs & Architecture:
- **Immutability:** Always `features[window_key].copy()`, return new dict
- **NaN handling:** Empty windows → NaN (drop later in modeling)
- **Signature pattern:** `(sensors, features, *, window_key, ...)`
- **Pipeline defaults:** Use `add_f()` helper

### From Decorators:
- Feature functions are NOT decorated (no `@transform_all_sensors`)
- Direct dict manipulation: `{**features, window_key: modified_df}`
- Multi-source: `source=["sensors", "features"]`, dest=`"features"`

---

## VALIDATION CRITERIA - ✅ ALL MET!

**Phase 1 (Raw Features) - ✅ COMPLETE:**
- ✅ `acc_rms`, `acc_std`, `acc_p2p`, `zero_crossing_rate`, `acc_kurtosis` implemented & tested
- ✅ Pipeline runs without errors
- ✅ Feature DataFrame has 5 raw feature columns
- ✅ Values plausible on real data
- ✅ Smoke test successful

**Phase 2 (Velocity Extraction) - ✅ COMPLETE:**
- ✅ `compute_window_velocity` implemented with 4-factor confidence
- ✅ Columns `v` and `v_confidence` added
- ✅ 10 unit tests + 1 integration test passing
- ✅ GPS confidence algorithm validated

**Phase 3 (Velocity Normalization) - ✅ COMPLETE:**
- ✅ `normalize_features_by_velocity` implemented (133 lines)
- ✅ Config integration complete
- ✅ Multiple pipeline calls pattern working
- ✅ Hard threshold + extensibility placeholders in place
- ✅ 10 unit tests + 1 integration test written
- ✅ Feature DataFrame has 15 total columns (4 temporal + 2 velocity + 5 raw + 4 normalized)

**✅ READY FOR MODELING:**
- ✅ All 3 feature engineering phases complete
- ✅ All tests written and validated
- ✅ Pipeline produces 15-column feature DataFrame
- ✅ Documentation updated (sprint plan, decisions log, protocol files)

---

## FILES FOR REFERENCE

**Project docs:**
- `ADRs.md`: Architecture decisions
- `Protokoll_Feature_Engineering_MVP.md`: Full session protocol with checkboxes
- `Milestone_Matrix_30_09_25.md`: MVP timeline

**Key source files:**
- `src/untergrund/runners/features.py`: ⚠️ CURRENT WORK FILE
- `src/untergrund/runners/preprocess.py`: Example patterns
- `src/untergrund/context.py`: Ctx dataclass

**Tests:**
- `tests/test_preprocessing.py`: Function test examples
- `tests/test_ctxpipeline_routing.py`: Pipeline tests

---

## EXPECTED CLUSTERING BEHAVIOR (Prediction)

**With 15 features (5 raw + 4 normalized + 2 velocity + 4 temporal), K-Means should distinguish:**

**Cluster A: Glatter Asphalt**
- Raw: RMS = niedrig, ZCR = niedrig, Kurtosis = niedrig, P2P = niedrig, STD = niedrig
- Normalized: RMS_vnorm = niedrig, ZCR_vnorm = niedrig (konsistent über Geschwindigkeiten)
- Velocity: v = variabel, v_confidence = hoch (glatte Strecke → stabiles GPS)

**Cluster B: Kopfsteinpflaster (gleichmäßig)**
- Raw: RMS = hoch, ZCR = hoch, **Kurtosis = niedrig** ✅, P2P = mittel, STD = hoch
- Normalized: **RMS_vnorm, ZCR_vnorm = konstant** (geschwindigkeitsunabhängig!)
- Velocity: v = variabel, v_confidence = mittel-hoch

**Cluster C: Asphalt + Schlaglöcher (ungleichmäßig)**
- Raw: RMS = mittel, ZCR = niedrig, **Kurtosis = hoch** ✅, **P2P = sehr hoch** ✅, STD = mittel
- Normalized: Vnorm features zeigen Events auch bei niedriger Geschwindigkeit
- Velocity: v = variabel, v_confidence kann niedrig sein (Schocks → GPS-Drift)

**Cluster D: Schotter/Feldweg (chaotisch)**
- Raw: RMS = sehr hoch, ZCR = sehr hoch, Kurtosis = mittel-hoch, P2P = hoch, STD = sehr hoch
- Normalized: Vnorm features sehr hoch (auch normalisiert rau)
- Velocity: v = meist niedrig, v_confidence = mittel (holprig → instabiles GPS)

**Key differentiators:**
- **Velocity-normalized features**: Enable speed-independent surface comparison! 🎯
- **Kurtosis**: Trennt B (gleichmäßig) von C (Events) - velocity-independent by nature
- **P2P**: Identifiziert einzelne krasse Stöße (Debugging)
- **ZCR**: Trennt hochfrequent (Kopfstein) von niederfrequent (Asphalt)
- **v_confidence**: Kann Cluster-Qualität indizieren (glatte Straße → hohe Confidence)

---

**END CONTEXT - ✅ ALL 3 PHASES IMPLEMENTED! Ready for Model Stage (K-Means Clustering)**
**Last Updated:** 2025-12-21
