# M3 Specification: Phase 2 – Velocity Extraction & Validation

**Last Updated:** 2025-12-21
**Status:** ✅ IMPLEMENTED
**Related:** M3_Features.md (Parent Spec)

**Ziel:** GPS-Speed extrahieren + numerischen Validierungswert berechnen

---

## 📋 KONTEXT

### Was wurde entschieden:
- GPS-Sensor liefert `speed` direkt (m/s) → keine Haversine-Berechnung nötig
- Zweispaltiges Output: `v` (float) + `v_confidence` (float 0.0-1.0)
- Confidence = numerischer Validierungswert (NICHT bool)
- KISS-Prinzip: Vertraue dem Sensor, minimale aber sinnvolle Validation

### Warum numerisch statt bool:
- Flexibilität: Threshold später setzbar (z.B. >0.7 = "valid")
- Debugging: Graduelle Abstufung sichtbar
- Zukunft: Imputation/Interpolation anhand Confidence möglich

---

## 🔧 FUNKTION: `compute_window_velocity`

### Signatur:
```python
def compute_window_velocity(
    sensors: dict[str, pd.DataFrame], 
    features: dict[str, pd.DataFrame], 
    *, 
    window_key: str,
    sensor_name: str = "Location"
) -> dict[str, pd.DataFrame]:
```

### Input:
- `sensors["Location"]`: DataFrame mit Spalten `speed`, `speedAccuracy`
- `features[window_key]`: DataFrame mit `start_utc`, `end_utc`

### Output:
- `features[window_key]` mit **2 neuen Spalten**:
  - `v`: float (m/s) - Median-Geschwindigkeit im Fenster
  - `v_confidence`: float (0.0-1.0) - Validierungswert

---

## 🧮 CONFIDENCE-BERECHNUNG (4 Faktoren)

### **Faktor 1: speedAccuracy (Hauptfaktor, 80% Gewicht)**

**Quelle:** `speedAccuracy` aus Location-Sensor (m/s)

**Logik:**
```
Niedriger Wert = besser
Typisch: 0.5 - 3.0 m/s

Formel (linear mapping):
confidence_base = max(1.0 - (speedAccuracy / 5.0), 0.0)

Beispiele:
0.5 m/s → 0.90
1.0 m/s → 0.80
2.0 m/s → 0.60
3.0 m/s → 0.40
5.0+ m/s → 0.00
```

**Begründung:** Sensor kennt seine eigene Unsicherheit am besten

---

### **Faktor 2: n_points (Robustheit, leichte Abwertung)**

**Quelle:** Anzahl gültiger GPS-Punkte im Fenster

**Logik:**
```
1 Punkt  → penalty = -0.15  (Einzelmessung unsicher)
2 Punkte → penalty = -0.05  (Median schon robuster)
3+ Punkte → penalty = 0.0   (Median sehr robust)
```

**Begründung:** Median aus mehreren Punkten filtert Ausreißer besser

---

### **Faktor 3: Speed-Range (Showstopper, harte Grenzen)**

**Quelle:** Berechneter Median-Speed `v`

**Logik:**
```
if v < 0.3 m/s (< 1.08 km/h):
    → SHOWSTOPPER: confidence = 0.0
    → Begründung: Stillstand, GPS-Noise dominiert

if v > 20.0 m/s (> 72 km/h):
    → SHOWSTOPPER: confidence = 0.0
    → Begründung: Unrealistisch für Fahrrad (außer Downhill-Profi)

if 0.3 <= v <= 20.0:
    → Plausibel, kein Penalty
```

**Begründung:** Physikalisch unrealistische Werte sofort ausschließen

---

### **Faktor 4: Stabilität/Flattern (NICHT im MVP implementiert)**

**Status:** PLATZHALTER - gibt aktuell **keinen Penalty** (neutral)

**Zukünftige Logik (Post-MVP):**
```
Coefficient of Variation (CV) = std(speeds) / mean(speeds)

if CV > 1.0:  # ABSURDES Flattern (z.B. 5→50→8 m/s)
    penalty = -0.2
else:
    penalty = 0.0
```

**Warum erstmal NICHT:**
- Bei echter Beschleunigung auch hoher CV (False Positive)
- Braucht temporale Analyse (zu komplex für MVP)
- Faktor 1-3 reichen für robuste Validation

**Implementierung:** Variable einbauen, aber `penalty_stability = 0.0` hardcoden

---

## 📐 AGGREGATION

### Formel:
```python
# 1. Prüfe Showstopper (Faktor 3)
if v < 0.3 or v > 20.0:
    v_confidence = 0.0
    return

# 2. Berechne Base (Faktor 1)
confidence_base = max(1.0 - (mean_speedAccuracy / 5.0), 0.0)

# 3. Penalty für wenige Punkte (Faktor 2)
if n_points == 1:
    penalty_points = -0.15
elif n_points == 2:
    penalty_points = -0.05
else:
    penalty_points = 0.0

# 4. Penalty für Stabilität (Faktor 4 - MVP: deaktiviert)
penalty_stability = 0.0  # TODO Post-MVP: CV-basiert

# 5. Aggregation
v_confidence = max(confidence_base + penalty_points + penalty_stability, 0.0)
v_confidence = min(v_confidence, 1.0)  # cap bei 1.0
```

**Wichtig:** Showstopper überschreibt ALLES (keine Aggregation)

---

## 🧪 TEST-SZENARIEN

### Szenario A: Perfekt
```
Input:
- n_points = 4
- speedAccuracy = 0.8 m/s
- speeds = [8.1, 8.0, 7.9, 8.2] m/s
- v_median = 8.05 m/s

Expected:
- v = 8.05
- confidence_base = 1.0 - (0.8/5.0) = 0.84
- penalty_points = 0.0
- penalty_stability = 0.0
- v_confidence = 0.84 ✅
```

### Szenario B: Mittelmäßig
```
Input:
- n_points = 2
- speedAccuracy = 2.0 m/s
- speeds = [11.5, 12.5] m/s
- v_median = 12.0 m/s

Expected:
- v = 12.0
- confidence_base = 1.0 - (2.0/5.0) = 0.6
- penalty_points = -0.05
- penalty_stability = 0.0
- v_confidence = 0.55 🟡
```

### Szenario C: Showstopper (zu schnell)
```
Input:
- n_points = 3
- speedAccuracy = 0.5 m/s (eigentlich gut!)
- speeds = [24, 26, 25] m/s
- v_median = 25.0 m/s (90 km/h)

Expected:
- v = 25.0
- SHOWSTOPPER: v > 20.0
- v_confidence = 0.0 ❌
```

### Szenario D: Showstopper (Stillstand)
```
Input:
- n_points = 3
- speedAccuracy = 1.0 m/s
- speeds = [0.1, 0.2, 0.15] m/s
- v_median = 0.15 m/s

Expected:
- v = 0.15
- SHOWSTOPPER: v < 0.3
- v_confidence = 0.0 ❌
```

### Szenario E: Keine GPS-Daten
```
Input:
- n_points = 0 (Fenster ohne GPS)

Expected:
- v = NaN
- v_confidence = NaN
- Warning ausgeben
```

---

## 🔍 IMPLEMENTIERUNGS-DETAILS

### GPS-Punkte filtern (vor Median):
```python
# Nur gültige Messungen
valid_mask = (window_data["speed"] >= 0) & (window_data["speedAccuracy"] >= 0)
valid_speeds = window_data.loc[valid_mask, "speed"]
valid_accuracies = window_data.loc[valid_mask, "speedAccuracy"]

if len(valid_speeds) == 0:
    v = NaN
    v_confidence = NaN
    continue
```

### Aggregation im Fenster:
```python
v = valid_speeds.median()  # Median (robust!)
mean_speedAccuracy = valid_accuracies.mean()  # Mean Accuracy
n_points = len(valid_speeds)
```

### NaN-Handling:
```python
# Counter für Warnings
nan_count = 0

if len(valid_speeds) == 0:
    v_values.append(np.nan)
    v_confidence_values.append(np.nan)
    nan_count += 1
    continue

# Nach Loop:
if nan_count > 0:
    print(f"[Warning] compute_window_velocity: {nan_count} windows had no valid GPS data.")
```

---

## 📊 OUTPUT-STRUKTUR

### Neue Spalten in `features[window_key]`:

| Spalte | Typ | Beschreibung | Wertebereich |
|--------|-----|--------------|--------------|
| `v` | float | Median-Geschwindigkeit (m/s) | 0.0 - 20.0 (oder NaN) |
| `v_confidence` | float | Validierungswert | 0.0 - 1.0 (oder NaN) |

### Beispiel-DataFrame (nach Phase 2):
```
| window_id | start_utc | end_utc | v    | v_confidence | acc_rms | ... |
|-----------|-----------|---------|------|--------------|---------|-----|
| 0         | ...       | ...     | 4.2  | 0.78         | 2.1     | ... |
| 1         | ...       | ...     | 8.5  | 0.84         | 3.8     | ... |
| 2         | ...       | ...     | 0.15 | 0.0          | 0.8     | ... | <- Showstopper
| 3         | ...       | ...     | NaN  | NaN          | 2.5     | ... | <- Keine GPS
```

---

## 🎯 PHASE 3 VORBEREITUNG

### Normalisierung (später):
```python
# In Phase 3 dann:
if v_confidence > 0.0 and v > 0.01:  # Threshold flexibel
    acc_rms_vnorm = acc_rms / (v**1.5 + 0.01)
else:
    acc_rms_vnorm = NaN
```

### Threshold-Beispiele (für spätere Nutzung):
```python
# Debug/Analysis
high_quality = v_confidence >= 0.7   # vertrauenswürdig
medium_quality = 0.4 <= v_confidence < 0.7  # grenzwertig
low_quality = v_confidence < 0.4     # fragwürdig

# Clustering (MODEL Stage)
valid_for_normalization = v_confidence >= 0.5  # Beispiel-Threshold
```

---

## ⚠️ WICHTIGE HINWEISE

### Was dieser Score NICHT ist:
- ❌ KEINE temporale Konsistenz (Vergleich mit Nachbarfenstern)
- ❌ KEINE Interpolation/Imputation
- ❌ KEINE komplexe Physik-Modellierung
- ❌ KEIN Machine Learning

### Was er IST:
- ✅ Sensor-basierte Qualitätseinschätzung
- ✅ Harte Grenzen für Unsinn-Werte
- ✅ Transparent und nachvollziehbar
- ✅ MVP-tauglich (KISS)

### Erweiterungen (Post-MVP):
- Faktor 4 aktivieren (Stabilität via CV)
- Temporale Konsistenz (neue VALIDATE_VELOCITY Stage)
- Horizontal Accuracy einbeziehen
- Platform-spezifische GPS-Qualität (Android vs iOS)

---

## 📝 CHECKLIST FÜR IMPLEMENTIERUNG

- [x] Funktion `compute_window_velocity` erstellen
- [x] GPS-Punkte filtern (speed >= 0, speedAccuracy >= 0)
- [x] Median-Berechnung für v
- [x] Mean-Berechnung für speedAccuracy
- [x] Showstopper-Check (0.3 <= v <= 20.0)
- [x] Confidence-Base aus speedAccuracy (Faktor 1)
- [x] Penalty für n_points (Faktor 2)
- [x] Penalty für Stabilität = 0.0 hardcoden (Faktor 4 Platzhalter)
- [x] Aggregation: confidence = base + penalties
- [x] NaN-Handling für Fenster ohne GPS
- [x] Warnings für NaN-Fenster ausgeben
- [x] In `run_features()` Pipeline einhängen
- [x] Test mit echten Daten (Smoke-Test)
- [x] Plausibilitäts-Check: v-Werte realistisch? Confidence sinnvoll?

---

## 🚀 INTEGRATION IN PIPELINE

### In `src/untergrund/runners/features.py`:

```python
def run_features(ctx: "Ctx") -> "Ctx":
    w_key = select_window_key(ctx, "cluster")
    pipeline = CtxPipeline()
    
    def add_f(fn, **kwargs):
        pipeline.add(fn, source=["sensors","features"], dest="features", 
                     fn_kwargs={"window_key": w_key, **kwargs})
    
    # Phase 2: Velocity (NEU - vor Raw Features!)
    add_f(compute_window_velocity)
    
    # Phase 1: Raw Features
    add_f(acc_rms)
    add_f(acc_std)
    add_f(acc_p2p)
    add_f(zero_crossing_rate)
    add_f(acc_kurtosis)
    
    # Phase 3: Normalization (später)
    # add_f(normalize_features_by_velocity, ...)
    
    # Taps
    pipeline.tap(row_col_nan_dur_freq, source="features")
    pipeline.tap(head_tail, source="features")
    
    return pipeline(ctx)
```

---

**Ende der Spezifikation**
