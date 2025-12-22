# Runner-Leitfaden (Contract)

**Last Updated:** 2025-12-21
**Status:** ✅ Active
**Related ADRs:** ADR-001, ADR-002

Jeder Runner ist eine **Stage** der Pipeline
`INGEST → SELECT → PREPROCESS → WINDOW → FEATURES → MODEL → EXPORT`.

Dieser Leitfaden definiert die minimalen Regeln für alle Runner.

---

## TL;DR

- Immer **`Ctx → Ctx`**.
- Harte Fehler → **Exception**.
- Keine Arbeit → **No‑Op + Hinweis**.
- Runner bleiben **schlank**, Logik in Pipelines.

---

## Signatur

```python
def run_<stage>(ctx: Ctx) -> Ctx:
    ...
```
- **Input:** immer `Ctx`
- **Output:** immer `Ctx` (niemals `None`)

---

## Verhalten

- **Harte Fehler** (z. B. defekte Datei, fehlende Pflichtspalten)  
  → Exception auslösen (`raise RuntimeError(...)` oder spezifischer).

- **Keine Arbeit zu erledigen** (z. B. gewünschter Sensor nicht vorhanden, nichts zu tun)  
  → **No‑Op:** `ctx` unverändert zurückgeben und kurz hinweisen (aktuell `print`, später Logging).

---

## Regeln

- Runner enthalten nur die **Orchestrierung** (Zusammenstecken der Pipelines/Steps).
- Fachlogik in **Pipelines** bzw. deren **pure Functions**.
- Runner‑spezifische Besonderheiten als **Docstring/Kommentar** in der jeweiligen Datei dokumentieren.
- I/O nur dort, wo es vorgesehen ist (Ingest und Export).


