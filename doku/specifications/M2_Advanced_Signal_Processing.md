# M2 Reference: Advanced Signal Processing

**Last Updated:** 2025-12-21
**Status:** 🟡 PLANNING (Future Enhancements)
**Related:** M2_Preprocessing.md (Main Spec)

*Ziel: Rohsensorik in eine robust **klassifizierbare** Signalform bringen. Diese Referenz ist absichtlich Code‑nah (HOW), damit die Implementierung ohne Ratespiel gelingt.*

**Hinweis:** Diese 12 Bausteine sind für zukünftige Optimierungen vorgesehen. Basis-Preprocessing (M2_Preprocessing.md) ist bereits implementiert.

---

## Priorisierung & Häkchen
Die 12 Bausteine sind nach **MVP‑Tauglichkeit** priorisiert. Hake ab, wenn ein Punkt inkl. Tests erledigt ist.

- [x] **1) High‑Pass Filter (Beschleunigung)** — `unerlässlich`
  - **WHAT**  
    `hpf_remove_slow_motion(acc, fs_hz, fc_hz≈2.0, order=4)` entfernt quasi‑statische Anteile (Neigung, langsame Körperbewegungen) aus `Accelerometer`.
  - **WHY**  
    Fahrbahnvibrationen liegen typischerweise **> 2 Hz**; darunter dominieren Haltung/Drift. HPF macht die Oberflächen‑Signatur sichtbar.
  - **HOW (Implementierungshinweise)**  
    - **Input:** `pd.DataFrame` mit Spalten `x, y, z` und `DatetimeIndex` in UTC (`time_utc`), gleichmäßiger Takt (ggf. nach Resampling).  
    - **Design:** *Zero‑phase* Butterworth (IIR) mit `scipy.signal.butter` + `filtfilt` (keine Phasenverschiebung).  
    - **Grenzfrequenz:** `fc_hz = 2.0` (Startwert). Normieren: `wn = fc_hz / (fs_hz/2)`.  
    - **Order:** `4` als robuster Default (steile Trennung, noch stabil).  
    - **NaN‑Sicherheit:** Segmentiere zusammenhängende gültige Abschnitte (`~isna().any(axis=1)`), filtere **je Segment**, füge zusammen; NaNs bleiben erhalten.  
    - **Pseudocode:**
      ```python
      def hpf_remove_slow_motion(df, *, fs_hz: float, fc_hz: float = 2.0, order: int = 4):
          b, a = butter(order, fc_hz/(fs_hz/2), btype="highpass")
          return apply_filter_segmentwise(df[["x","y","z"]], b, a, mode="filtfilt")
      ```
    - **Tests (Mini‑Synthetik):** addiere einem 10 Hz‑Sinus einen 0.3 Hz‑Drift; nach HPF ≈ Drift < −20 dB, 10 Hz‑Amplitude ≈ unverändert.

- [x] **2) High‑Pass Filter (Gyro)** — `unerlässlich`
  - **WHAT**  
    `gyro_hpf_remove_bias(gyro, fs_hz, fc_hz≈0.3, order=2)` entfernt Gyro‑Bias/Drift.
  - **WHY**  
    Wandernder Nullpunkt verschmiert Energie‑Masse und verfälscht Rotationsdynamik.
  - **HOW**  
    - `fc_hz=0.3`, `order=2` genügt (Bias langsam).  
    - Gleiches Segment‑/NaN‑Handling wie oben.  
    - Test: Konstante + 5 Hz‑Sinus → Konstante eliminiert, 5 Hz bleibt.

- **2.1) Highpass (1 u. 2) zusammengefasst**
    - [x] -> alles wird mit einer Funktion "high_pass_filter" gefiltert
    - [x] Parameter in die Config schreiben für alle Sensoren
    - [x] .add(), HP-Filter (je Sensor) der Pipeline hinzufügen

 
- [x] **3) Anti‑Aliasing‑Filter vor Downsampling** — `unerlässlich`
  - **WHAT**  
    `anti_alias_lpf_before_downsample(x, fs_in_hz, fs_out_hz, fc_hz≈0.45*fs_out_hz/2)` beschneidet Frequenzen oberhalb der neuen Nyquist‑Grenze.
  - **WHY**  
    Verhindert **Aliasing** (hochfrequentes „Falten“ in tiefe Frequenzen) beim Downsampling.
  - **HOW**  
    - **Nur** anwenden, wenn `fs_out_hz < fs_in_hz`.  
    - Cutoff konservativ: `fc_hz = 0.45 * (fs_out_hz/2)`; `order=4` IIR *oder* kurzer Kaiser‑FIR, je nach Präferenz.  
    - Downsampling danach per `df.resample(rule).agg(...)` oder `scipy.signal.decimate` (bei exakt ganzzahligem Faktor).  
    - Test: 30 Hz‑Sinus auf 25 Hz Zielrate → ohne LPF aliasiert, mit LPF bleibt Dämpfung kontrolliert.

- [ ] **4) Achs‑Ausrichtung zum Fahrradrahmen** — `nice to have`
  - **WHAT**  
    `axis_aligner_to_bike_frame(acc, gyro, orientation)` rotiert IMU‑Achsen in ein konsistentes Bike‑Koordinatensystem (vor/zurück, quer, hoch).
  - **WHY**  
    Montagewinkel und Haltung variieren; Alignment verbessert Vergleichbarkeit und Feature‑Stabilität.
  - **HOW**  
    - **Pfad A (Orientation vorhanden):** Nutze Quaternion/Rotationsmatrix (`GameOrientation`) → rotiere `acc[x,y,z]` und `gyro[x,y,z]` ins Frame.  
    - **Pfad B (kein Orientation):** Führe zusätzlich eine **Magnitude‑Spur** `acc_mag = sqrt(x²+y²+z²)` und arbeite dort orientierungsinvariant.  
    - Test: Bekannte künstliche Rotation → nach Alignment stimmen Achsen mit Ground‑Truth überein (Toleranz < 1e‑6).

- [x] **5) NaN‑sichere Filterung** — `unerlässlich`
    --> Generelles NaN-Handling als Funktion im Basic-Preprocessing!
  - **WHAT**  
    `nan_safe_filtering(x)` stellt sicher, dass Filter **nie** über NaNs laufen.
  - **WHY**  
    Filter über Lücken erzeugen Ringing/Artefakte, `filtfilt` kann fehlschlagen.
  - **HOW**  
    - Erzeuge Maske `valid = ~df[cols].isna().any(axis=1)`.  
    - Finde Segmente mit `valid`‑Lauflaengen (groupby auf Wechsel).  
    - Filtere je Segment ab **Mindestlänge** (z. B. > 3×Filterlänge), sonst Segment unverändert lassen.  
    - Erhalte NaN‑Lagen exakt bei.  
    - Test: künstliche NaN‑Lücke → keine Werte „überspringen“, Länge gleich.
  ----> Als eigene Funktion "nan_handling" implementiert!!!

- [ ] **6) Spike‑ & Sättigungs‑Erkennung** — `nice to have`
  - **WHAT**  
    `saturation_and_spike_guard(x, max_abs=phys_limit, median_win=5, clip_q=None)` erkennt harte Ausreißer/Sensor‑Clipping.
  - **WHY**  
    Kurzzeitige Spitzen ruinieren Varianz/Energie‑Features.
  - **HOW**  
    - **Heuristik 1:** Median‑Filter (Fenster 3–7) → markiere Abweichungen `>|k·MAD|`.  
    - **Heuristik 2:** Clipping auf `[-max_abs, +max_abs]` (physikalisch), **Zähler** `n_spikes` führen.  
    - Optional Quantil‑Clipping `clip_q=(0.001, 0.999)` für weiche Begrenzung.  
    - Test: injiziere einzelne ±20g‑Spikes → Zähler > 0, amplitude nach Clipping ≤ max_abs.

- [ ] **7) Normalisierung pro Session** — `erst für globale vergleichbarkeit wichtig -> dann unerlässlich`????????????
  - **WHAT**  
    `normalize_per_session(x, mode="robust"|"zscore")` skaliert je Fahrt/Session.
  - **WHY**  
    Gerätespezifische Level‑Shifts und Montage erzeugen Offset/Skalierungen; Normalisierung stabilisiert Features und Klassifikator.
  - **HOW**  
    - **robust:** `x' = (x - median) / MAD` (skaliertes MAD).  
    - **zscore:** `x' = (x - μ) / σ`.  
    - Achsen separat behandeln (`x,y,z`), `gyro` getrennt von `acc`.  
    - **Artefakte/Metrics:** in `artifacts["metrics"][sensor]` `{"norm": "robust", "median": ..., "mad": ...}` speichern.  
    - Test: synthetischer Offset/Skalierung → nach Normierung Mittel ≈ 0, Skala ≈ 1.

- [ ] **8) Bandpass „Road‑Vibes“ (2–40 Hz)** — `nice to have`
  - **WHAT**  
    `bandpass_road_vibes(acc, fs_hz, f_low≈2, f_high≈40, order=4)` fokussiert das Vibrationsband der Fahrbahn.
  - **WHY**  
    Viele oberflächenrelevante Strukturen liegen in 2–40 Hz; Bandpass reduziert Off‑Band‑Rauschen.
  - **HOW**  
    - Implementiere als Kaskade HPF(2 Hz) + LPF(40 Hz) **oder** direktes Bandpass‑Design.  
    - Reihenfolge zu 1/3 abstimmen, um doppelte Filterung zu vermeiden (siehe Pipeline unten).  
    - Test: Multi‑Sinus (1 Hz + 10 Hz + 60 Hz) → 10 Hz bleibt, 1 Hz/60 Hz stark gedämpft.

- [ ] **9) Notch‑Filter (50 Hz Netz)** — `ehr unwichtig`
  - **WHAT**  
    `notch_line_hum(x, f0=50, Q≈30)` entfernt Netz‑Brummen, v. a. bei Ladevorgängen.
  - **WHY**  
    Sporadisch relevant; sonst Over‑Engineering.
  - **HOW**  
    - IIR‑Notch über `iirnotch(w0, Q, fs)`; nur anwenden, wenn Spektrum klare 50 Hz‑Spitze zeigt (Heuristik: Peak > x dB über Nachbarn).  
    - Test: f0‑Peak künstlich injizieren → nach Notch sinkt Peak deutlich (> 15 dB).

- [ ] **10) Savitzky‑Golay‑Glättung** — `nice to have`
  - **WHAT**  
    `savgol_denoise(x, window_samples≈7–11, poly=2–3)` glättet sanft ohne Phasenverschiebung.
  - **WHY**  
    Erhält Peak‑Form besser als Moving‑Average; nützlich nach HPF/AA.
  - **HOW**  
    - `scipy.signal.savgol_filter` je Achse, nur auf **gleichmäßig getakteten** Daten.  
    - Fenster **ungerade**, `window <= 0.2 * fs_hz` als grober Start.  
    - Test: weißes Rauschen auf Sinus → SNR‑Verbesserung messbar, Phase ≈ 0.

- [ ] **11) Schwerkraft‑Schätzung & Subtraktion** — `nice to have`
  - **WHAT**  
    `gravity_lowpass_reference(acc, fs_hz, fc_hz≈0.4)` schätzt `g` via starkem LPF und subtrahiert es von `acc` → dynamische Beschleunigung.
  - **WHY**  
    Alternative/Ergänzung zu 1); manchmal stabiler bei Montageänderungen.
  - **HOW**  
    - LPF (`fc≈0.3–0.5 Hz`, order=2–4) → `g_est`.  
    - `acc_dyn = acc - g_est`.  
    - Nicht gleichzeitig *und* HPF 2 Hz erzwingen; sonst doppelte Trennung.  
    - Test: statische Lage + Vibration → statischer Anteil ≈ g, nach Subtraktion bleibt Vibration.

- [ ] **12) Achsweise Energie‑Normalisierung** — `ehr unwichtig`
  - **WHAT**  
    `per_axis_energy_balance(acc|gyro, mode="rms"|"var")` gleicht Achsdominanz aus.
  - **WHY**  
    Montagewinkel können eine Achse bevorzugen; Balancing reduziert Bias.
  - **HOW**  
    - Skaliere Achsen, so dass `RMS(x)=RMS(y)=RMS(z)` (oder gleiche Varianz).  
    - Nur nach 1)/7) sinnvoll; nicht doppelt normieren.  
    - Test: gleiche Energie nach Skalierung, Summe‑RMS bleibt stabil.

---

## Empfohlene Reihenfolge (MVP & danach)
**MVP (nur „unerlässlich“):**  
`nan_safe_filtering` → `hpf_remove_slow_motion(acc)` → `gyro_hpf_remove_bias()` → `anti_alias_lpf_before_downsample()` → `normalize_per_session()`

**Erweiterungen (Qualität):**  
`axis_aligner_to_bike_frame` → `saturation_and_spike_guard` → `bandpass_road_vibes` → `savgol_denoise` → `gravity_lowpass_reference` → `per_axis_energy_balance` → `notch_line_hum (on-demand)`

---

## Contracts & Signaturen (Vorschlag, Code‑nah)

```python
@transform_all_sensors
def hpf_remove_slow_motion(df: pd.DataFrame, *, fs_hz: float, fc_hz: float = 2.0, order: int = 4,
                           sensor_name: str | None = None) -> pd.DataFrame: ...

@transform_all_sensors
def gyro_hpf_remove_bias(df: pd.DataFrame, *, fs_hz: float, fc_hz: float = 0.3, order: int = 2,
                         sensor_name: str | None = None) -> pd.DataFrame: ...

@transform_all_sensors
def anti_alias_lpf_before_downsample(df: pd.DataFrame, *, fs_in_hz: float, fs_out_hz: float,
                                     cutoff_hz: float | None = None, order: int = 4,
                                     sensor_name: str | None = None) -> pd.DataFrame: ...
```
- **Parametrisierung über Pipeline:**  
  `pipeline.add(hpf_remove_slow_motion, source="sensors", fn_kwargs={"fs_hz": 50, "fc_hz": 2.0})`  
  (später via `with_kwargs` / `fn_kwargs`, siehe ADR‑007).

**Hilfsfunktion (NaN‑Segmentierung, einmal zentral):**
```python
def apply_filter_segmentwise(df_xyz: pd.DataFrame, b, a, *, mode: str = "filtfilt") -> pd.DataFrame:
    # findet gültige Segmente und wendet Filter je Segment an; NaNs bleiben erhalten
    ...
```
**Samplerate‑Schätzer (falls `fs_hz` nicht in Config):**
```python
def estimate_fs_from_index(idx: pd.DatetimeIndex) -> float:
    dt = idx.to_series().diff().dropna().dt.total_seconds().median()
    return 1.0 / dt
```

---

## Defaults (Startwerte & Guardrails)
- **acc HPF:** `fc=2.0 Hz`, `order=4`, zero‑phase.  
- **gyro HPF:** `fc=0.3 Hz`, `order=2`.  
- **AA‑LPF:** `fc=0.45 * Nyquist(fs_out)`, `order=4`.  
- **Spike‑Guard:** `median_win=5`, optional `clip_q=(0.001, 0.999)`.  
- **Normalization:** `mode="robust"` (Median/MAD).  
- **Notch:** nur wenn Peak bei 50 Hz detektiert.

---

## Qualitäts‑Checks & Tests (pro Sensor)
- [ ] Spektrum vor/nach Filter (RMS in Bändern) plausibel.  
- [ ] NaN‑Positionen unverändert.  
- [ ] Gain‑Flatness im Passband (±1 dB).  
- [ ] Zero‑phase: Latenz ~ 0 (Impulsantwort symmetrisch).  
- [ ] Repro‑Metriken in `artifacts["metrics"]` gesichert.

---

## Hinweise zur Integration in PREPROCESS
- Filter nur nach **sauberem Zeitgitter** (Sort, Dedupe, Resampling).  
- **Keine** harte Kopplung an Decorator‑Interna; alle Parameter via `fn_kwargs`.  
- Metriken (z. B. `{"hp_acc": {"fc": 2.0, "order": 4}}`) in `artifacts` mitschreiben (Reporter‑Step).

---

*Version:* B4‑priorisiert‑v2 (ausführlich, code‑nah).  
*Änderungshistorie:* v1 (kurz) → v2 (HOW erweitert, Tests & Contracts ergänzt).
