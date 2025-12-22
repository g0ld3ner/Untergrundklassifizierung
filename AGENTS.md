# Repository Guidelines

## Project Structure & Modules
- Core package lives in `src/untergrund`; pipelines are assembled in `stages.py`, orchestrated via `orchestrator.py`, and executed by `run_stages` in `pipeline.py`.
- Stage-specific runners sit in `src/untergrund/runners/` (`ingest`, `select`, `preprocess`, `window`, `features`, `model`, `export`); shared helpers are in `src/untergrund/shared/`.
- `config.json` holds the pipeline configuration; `data/` contains sample input; `main.py` runs a full pass using the config.
- Tests reside in `tests/` with fixtures in `tests/data/`. Keep notebook experiments (e.g., `TEST_json_einlesen.ipynb`) out of the package code.

## Build, Test, and Development Commands
- Install editable package: `python -m pip install -e .` (uses `pyproject.toml`).
- Run pipeline locally with default config: `python main.py`.
- Execute all tests: `pytest`.
- Focus a test module: `pytest tests/test_ctxpipeline_routing.py -q`.

## Coding Style & Naming Conventions
- Python 3.12, 4-space indentation, and type hints where meaningful; prefer pure functions that accept/return dataclass-backed context (`Ctx`).
- Use `snake_case` for functions/variables, `CapWords` for classes, and descriptive names for pipeline steps (`acc_rms`, `hp_filter`, etc.).
- Keep runners side-effect free; mutate context via dataclass replacement rather than in-place modifications.
- When adding helpers, colocate them near the stage (e.g., `runners/preprocess.py`) and avoid hidden globals.

## Testing Guidelines
- Use `pytest`; new behavior should have `test_*.py` coverage in `tests/`. Mirror the module path when possible (e.g., `runners` → `tests/test_preprocessing.py`).
- Prefer small, deterministic fixtures; extend `tests/data/mini.json` or add new samples under `tests/data/`.
- For pipeline changes, add routing/contract checks similar to `test_ctxpipeline_routing.py` to catch wiring errors.

## Commit & Pull Request Guidelines
- Commits in history are short, descriptive, and occasionally German (e.g., “update README”, “Zwei Weitere Features Implementiert”). Follow that style: concise present-tense summaries, one logical change per commit.
- Include context in the body if decisions are non-obvious (config tweaks, math choices). Reference issues when relevant.
- For PRs, describe intent, key changes, and how to reproduce results; attach logs or screenshots for model/feature outputs when helpful. Ensure `pytest` passes before requesting review.

## Configuration & Data Hygiene
- Keep `config.json` checked in but avoid adding secrets; store large or sensitive datasets outside the repo (e.g., `local/`), and add paths to `.gitignore` if needed.
- Document non-default config values in the PR when they affect reproducibility (sampling rates, filters, window sizes).
