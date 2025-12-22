# Gemini Context: Untergrundklassifizierung

## Project Overview
**Untergrundklassifizierung** is a Python-based data processing pipeline designed to classify surface types (e.g., asphalt, gravel) using bicycle sensor data (Accelerometer, Gyroscope, Location). The project follows a strict functional, immutable architecture where data flows through a sequence of explicit stages.

## Architecture

### Core Concepts
*   **Context (`Ctx`):** The central, immutable data structure (`src/untergrund/context.py`) that holds all state:
    *   `sensors`: Raw/processed sensor time series (pandas DataFrames).
    *   `meta`: Global trip metadata.
    *   `features`: Computed features for classification.
    *   `preds`: Model predictions.
    *   `config`: Run configuration.
    *   `artifacts`: Provenance data (paths, hashes).
*   **Pipeline (`CtxPipeline`):** A routing engine (`src/untergrund/pipeline.py`) that executes pure functions against the `Ctx`. It handles:
    *   **Routing:** extracting specific fields (e.g., `sensors`) from `Ctx` to pass to functions.
    *   **Immutability:** updating `Ctx` via `dataclasses.replace` based on function outputs.
    *   **Tapping:** read-only inspection steps.
*   **Orchestrator:** (`src/untergrund/orchestrator.py`) runs the high-level stages sequentially.

### Stages
The pipeline is divided into distinct stages (`src/untergrund/runners/`):
1.  **Ingest:** Loads raw data from files (JSON).
2.  **Select:** Filters and isolates relevant sensors.
3.  **Preprocess:** Cleaning, resampling, filtering (Low-pass/High-pass).
4.  **Window:** Segments data into time windows.
5.  **Features:** Calculates statistical features (RMS, ZCR, etc.).
6.  **Model:** (In Progress) Clustering/Classification (e.g., K-Means).
7.  **Export:** Saves results and artifacts.

## Key Files
*   `main.py`: Entry point. Loads `config.json`, creates `Ctx`, and runs stages.
*   `config.json`: Configuration for all pipeline stages (paths, sample rates, filter parameters).
*   `src/untergrund/context.py`: Definition of the `Ctx` dataclass.
*   `src/untergrund/pipeline.py`: The `CtxPipeline` logic.
*   `src/untergrund/orchestrator.py`: Maps stages to their runner functions.

## Setup & Usage

### Installation
The project uses `setuptools`. Install in editable mode:
```bash
pip install -e .
```

### Running the Pipeline
Execute the main script to run the full pipeline based on `config.json`:
```bash
python main.py
```

### Testing
Run the test suite (pytest):
```bash
pytest
```

## Development Conventions
*   **Functional Style:** Prefer pure functions. Avoid side effects.
*   **Immutability:** The `Ctx` object is frozen. Use `CtxPipeline` to manage state transitions.
*   **Type Hinting:** Use strict type hints (`typing`, `dataclasses`) for all function signatures.
*   **Explicit Wiring:** Pipelines are manually composed in the runners, avoiding "magic" auto-wiring.
*   **Configuration:** All parameters (paths, constants) must be decoupled into `config.json`.
