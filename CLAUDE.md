# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Untergrundklassifizierung** is a Python-based sensor data processing pipeline that classifies bicycle riding surfaces (asphalt, gravel, etc.) from smartphone sensor data (accelerometer, gyroscope, GPS). The architecture emphasizes explicit pipelines, immutability, and functional composition.

## Essential Commands

### Setup & Installation
```bash
# Install package in editable mode
pip install -e .

# Activate virtual environment (if not already active)
source .venv/bin/activate
```

### Running the Pipeline
```bash
# Run full pipeline with default config
python main.py

# Config is in config.json - modify parameters there
```

### Testing
```bash
# Run all tests
pytest

# Run specific test module
pytest tests/test_ctxpipeline_routing.py -q

# Run specific test function
pytest tests/test_preprocessing.py::test_nan_handling -v
```

## Core Architecture Principles

### Immutable Context Pattern
All pipeline state flows through a **frozen `Ctx` dataclass** (src/untergrund/context.py):
- `sensors`: dict[str, pd.DataFrame] — Time-indexed sensor data
- `meta`: dict[str, Any] — Trip metadata
- `features`: dict[str, pd.DataFrame] — Window-level features
- `preds`: dict[str, pd.Series] — Model predictions (placeholder)
- `config`: dict[str, Any] — Configuration parameters
- `artifacts`: dict[str, Any] — Provenance/run metadata

**Never mutate Ctx directly** — use `dataclasses.replace()` via CtxPipeline.

### CtxPipeline Routing Engine
The `CtxPipeline` class (src/untergrund/pipeline.py) routes data between Ctx fields and pure functions:

```python
pipeline = CtxPipeline()

# Single source → dest (in-place if dest omitted)
pipeline.add(transform_fn, source="sensors")

# Multi-source → dest (dest required)
pipeline.add(compute_fn, source=["sensors", "config"], dest="features")

# Read-only inspection (no mutation)
pipeline.tap(inspector_fn, source="sensors")

# Parametrization
pipeline.add(fn, source="x", fn_kwargs={"param": value})
```

### Sensor Broadcast Decorators
The `@transform_all_sensors` and `@inspect_all_sensors` decorators (src/untergrund/shared/sensors.py) lift single-value functions to broadcast over sensor dictionaries:

```python
@transform_all_sensors
def nan_handling(df: pd.DataFrame, *, sensor_name: str | None = None) -> pd.DataFrame:
    # Applied per sensor, sensor_name injected automatically
    ...

# Usage with filtering
pipeline.add(
    nan_handling.select(include=["Accelerometer"]),
    source="sensors"
)

# Early parameter binding
pipeline.add(
    resample.with_kwargs(target_rate=100),
    source="sensors"
)
```

**Reserved parameter**: `sensor_name` (keyword-only) is auto-injected per sensor.

## Pipeline Stages

The pipeline flows through 7 sequential stages (src/untergrund/orchestrator.py):

1. **INGEST** (src/untergrund/runners/ingest.py)
   - Load raw JSON sensor data (SensorLogger format)
   - Extract metadata, build sensor dict

2. **SELECT** (src/untergrund/runners/select.py)
   - Filter sensors by config.sensor_list

3. **PREPROCESS** (src/untergrund/runners/preprocess.py)
   - Time conversion, NaN handling, deduplication
   - Anti-aliasing lowpass filter (Butterworth, order=6)
   - Resampling: IMU → 100 Hz, Location → 1 Hz
   - High-pass filter (2 Hz cutoff, removes DC/drift)
   - Validation: monotonic time index, no NaN, UTC timezone

4. **WINDOW** (src/untergrund/runners/window.py)
   - Segment time series into fixed windows
   - Default: 4s duration, 2s hop (50% overlap)

5. **FEATURES** (src/untergrund/runners/features.py)
   - Compute 5 base features: acc_rms, acc_std, acc_p2p, zero_crossing_rate, acc_kurtosis
   - Compute window velocity from GPS (with confidence scoring)
   - Calibrate velocity exponents via log-linear regression
   - Create velocity-normalized variants (*_vnorm): feature / (v^exponent + ε)

6. **MODEL** (src/untergrund/runners/model.py)
   - **Placeholder** — K-means clustering planned

7. **EXPORT** (src/untergrund/runners/export.py)
   - **Placeholder** — Save features, predictions, artifacts

## Key Implementation Details

### Signal Processing
- **Anti-aliasing**: Applied before resampling to prevent aliasing artifacts
  - Butterworth lowpass, order=6, cutoff=0.8 × (target_rate/2)
- **High-pass filter**: Removes gravity bias and sensor drift
  - Butterworth, order=4, cutoff=2 Hz
  - Applied to Accelerometer, Gyroscope only

### Feature Engineering
Features are designed to be velocity-independent for surface classification:

- **Amplitude features** (RMS, STD, P2P): ~v^1.5 velocity dependence
- **Frequency features** (ZCR): linear v-dependence
- **Shape features** (Kurtosis): velocity-independent (σ-normalized)

Velocity normalization process:
1. Compute raw features + window velocity
2. Calibrate exponent: log(feature) = log(a) + n·log(v)
   - Requires: ≥50 windows, R² ≥ 0.6, exponent ∈ [1.0, 3.0]
3. Normalize: feature_vnorm = feature / (v^exponent + ε)

### Configuration
All parameters live in **config.json**:
- `input_path`: Data file location
- `sensor_list`: Sensors to process (e.g., ["Accelerometer", "Location"])
- `window_duration_s`, `window_hop_s`: Windowing parameters
- `resample_imu`, `resample_location`: Resampling config
- `anti_aliasing_lowpass`: Per-sensor filter settings
- `hp_filters`: High-pass filter config
- `velocity_normalization`: Epsilon, confidence threshold, strategy

**Never hardcode parameters** — add them to config.json.

## Development Conventions

### Code Style
- Python 3.12, 4-space indentation
- Type hints required for function signatures
- Use `snake_case` for functions/variables, `CapWords` for classes
- Prefer pure functions: Ctx → Ctx (no side effects)

### Testing Requirements
- All new behavior needs test coverage in tests/
- Use fixtures from tests/data/mini.json or add new samples
- For pipeline changes, add routing tests like test_ctxpipeline_routing.py
- Ensure pytest passes before commits

### Commit Style
Commits are concise, present-tense, often in German:
- "update README"
- "Zwei Weitere Features Implementiert. (ZCR und Kurtosis)"
- "v-Normalisierung: -> details und finetuning folgen im nächsten commit!"

### Avoiding Over-Engineering
- **No abstractions for one-time operations** — keep it simple
- **No premature optimization** — solve the immediate problem
- **Explicit wiring only** — no magic config toggles or auto-discovery
- **Delete unused code completely** — no backwards-compatibility hacks

## Common Patterns

### Adding a New Preprocessing Step
1. Define pure function in src/untergrund/runners/preprocess.py:
   ```python
   @transform_all_sensors
   def my_transform(df: pd.DataFrame, *, sensor_name: str | None = None) -> pd.DataFrame:
       # ... transform logic
       return df
   ```

2. Add to pipeline in run_preprocess():
   ```python
   pipeline.add(my_transform, source="sensors")
   ```

3. Add test in tests/test_preprocessing.py

### Adding a New Feature
1. Define feature function in src/untergrund/runners/features.py:
   ```python
   def compute_my_feature(sensor_data: dict, window_df: pd.DataFrame) -> pd.DataFrame:
       # ... feature computation
       return feature_df
   ```

2. Add to feature pipeline in run_features()

3. Add test in tests/test_features.py

### Using Inspection Tools
All inspection helpers in src/untergrund/shared/inspect.py are tap-friendly:

```python
from src.untergrund.shared.inspect import row_col_nan_dur_freq, print_description

pipeline.tap(row_col_nan_dur_freq, source="sensors")
pipeline.tap(print_description, source="sensors")
```

## Data Handling

### Input Format
- SensorLogger JSON format (iOS/Android app)
- Required sensors: Accelerometer, Location
- Optional: Gyroscope, Magnetometer

### Test Data
- Small: tests/data/mini.json (~few KB)
- Medium: data/testdaten.json (6.3 MB)
- Full: data/Winterrunde.json (2 GB, not in repo)

### Output
- Features: DataFrame with columns [v, v_confidence, acc_rms, acc_rms_vnorm, ...]
- Index: window center timestamps (UTC timezone-aware)

## Troubleshooting

### Common Issues

**Pipeline fails at PREPROCESS stage:**
- Check sensor_list in config.json matches available sensors in data
- Verify anti_aliasing_lowpass config has entries for all sensors

**Features have NaN values:**
- Check velocity confidence threshold (default: 0.5)
- Verify GPS data quality (speedAccuracy, point count)

**Tests fail with "Ctx is immutable":**
- Never modify Ctx directly — use CtxPipeline or dataclasses.replace()

**Import errors:**
- Ensure pip install -e . was run
- Check Python version (requires ≥3.12)

## Documentation Structure

The `doku/` folder contains all project documentation (Git-tracked):

```
doku/
├── README.md                 # Documentation guide & conventions
├── architecture/
│   ├── Contracts.md          # Stage contracts, Ctx fields, data flow
│   └── ADRs.md               # Architecture Decision Records (append-only!)
├── specifications/
│   ├── M2_Preprocessing.md   # Preprocessing pipeline details
│   ├── M2_Advanced_Signal_Processing.md  # Filter theory
│   ├── M2.5_Windowing.md     # Windowing stage spec
│   ├── M3_Features.md        # Feature engineering (RMS, STD, P2P, ZCR, Kurtosis)
│   ├── M3_Phase2_Velocity.md # Velocity computation & normalization
│   └── M6_Enhancements.md    # Engineering improvements (planned)
├── roadmap/
│   ├── Milestones.md         # High-level milestone matrix
│   └── Issues_Template.md    # GitHub issue templates
└── protocols/
    └── Decision_Log.md       # Chronological session log (append-only!)
```

**Key Principles:**
- **Code is Single Source of Truth** — Documentation reflects implementation
- **Append-Only** for ADRs.md and Decision_Log.md (never modify old entries)
- **Status Labels**: 🟡 PLANNING, ✅ IMPLEMENTED, 🔴 DEPRECATED
- **Last Updated** header in every spec file

## Project Status

**Completed:**
- Pipeline infrastructure (7 stages: INGEST → SELECT → PREPROCESS → WINDOW → FEATURES → MODEL → EXPORT)
- Ingest, Select, Preprocess stages
- Windowing stage (4s windows, 2s hop, writes to `ctx.features["cluster"]`)
- Feature extraction (5 features + velocity normalization)
- Velocity normalization framework with exponent calibration
- Test coverage: 78 tests across 5 test modules
- Documentation review & sync with code (2025-12-21)

**In Progress:**
- Velocity normalization tuning (optimal exponents)

**TODO:**
- Model stage (K-Means clustering implementation)
- Export stage (CSV, GeoJSON, manifest)
- Streamlit visualization dashboard
- Structured logging (replace print statements)
- CLI/API interface

**Open Documentation Items** (see M2_Preprocessing.md):
- Metrics-Tap (sensor statistics collection)
- Gap Detection & Coverage Metrics

## Session History

For context on past decisions and implementation sessions, see `doku/protocols/Decision_Log.md`.

Key sessions:
- **2025-09-27**: Architecture foundation (ADR-001 to ADR-003)
- **2025-11-17/18**: Feature engineering Phase 1 (5 raw features)
- **2025-11-23**: Velocity computation with confidence scoring
- **2025-11-26**: Velocity normalization complete (all 3 phases)
- **2025-12-20**: Documentation refactoring (`local/` → `doku/`)
- **2025-12-21**: Documentation review & code synchronization
