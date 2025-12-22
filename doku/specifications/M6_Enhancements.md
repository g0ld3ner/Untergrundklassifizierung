# M6 Specification: Engineering Enhancements

**Last Updated:** 2025-12-21
**Status:** 🟡 PLANNING / ✅ PARTIALLY IMPLEMENTED
**Related ADRs:** ADR-007 (Parametrizable Steps), ADR-010 (Ctx Map-Only Policy - planned)

Dieses Dokument konsolidiert 3 Engineering-Erweiterungen für Milestone M6:
1. Pipeline Default Mechanismus (`.set_defaults()`)
2. Ctx-Struktur Vereinheitlichung (Map-Only Policy)
3. Visual Debugging & Inspection Tools

---

## 1️⃣ Pipeline Default Mechanismus

**Status:** 🟡 PLANNING

### WHAT
Einführung eines Mechanismus in `CtxPipeline`, um häufig wiederkehrende Parameter pro Pipeline-Instanz einmalig als Defaults zu definieren.

Ziel ist die Reduktion von Boilerplate in Stages (z. B. `run_preprocess`, `run_features`), ohne den bestehenden Funktionsvertrag zu verändern.

### WHY
- In allen Pipelines werden `source`, `dest` und `fn_kwargs` häufig wiederholt
- Viele Funktionen benötigen identische Kontexte (`cfg`, `feature_set` …)
- Der aktuelle Aufbau führt zu unnötiger Redundanz und erschwert das Lesen
- Defaults pro Instanz wahren die Klarheit, vermeiden aber Copy-Paste

### HOW

**Konzept:**
- Jedes Pipeline-Objekt besitzt eigene Default-Parameter (`self._defaults`)
- `.set_defaults()` überschreibt oder ergänzt sie
- `.add()` und `.tap()` verwenden sie automatisch, sofern der jeweilige Parameter nicht gesetzt ist

**Merge-Regeln:**

| Ebene | Vorrang |
|--------|----------|
| explizite Parameter im Funktionsaufruf | 🟢 höchster |
| zuvor gesetzte Pipeline-Defaults | 🟡 mittlerer |
| interne Standardwerte (`None`) | 🔴 niedrigster |

**Beispiel:**
```python
p = CtxPipeline()
p.set_defaults(source="sensors", fn_kwargs={"cfg": ctx.config})

p.add(time_to_index)                # bekommt source + cfg automatisch
p.add(nan_handling, fn_kwargs={"method": "drop"})  # überschreibt nur method
p.tap(print_info)                   # ebenfalls source="sensors"
```

**Auswirkungen:**
- ✅ Kein Einfluss auf bestehende Funktionalität
- ✅ Kein globaler Zustand: Defaults sind an Pipeline-Instanzen gebunden
- ✅ Klarer Datenfluss: Die finalen Parameter werden beim Hinzufügen berechnet

**Vorteile:**
- Saubere, minimale API-Erweiterung
- Reduziert Redundanz (weniger „visuelles Rauschen" in Stage-Definitionen)
- Intuitiv erweiterbar (z. B. spätere Defaults-Stacks oder Subpipelines)
- Kompatibel mit Decorator-Konzept (z. B. `.select()`)

**Nachteile:**
- Implizite Defaults können verwirren, wenn man Code liest ohne Pipeline-Definition zu kennen
- Debugging: "Woher kommt dieser Parameter?" (Mitigation: explizite Aufrufe haben Vorrang)

**Referenz:** `local/Protokoll_M6_Pipeline_Defaults.md`

---

## 2️⃣ Ctx-Struktur Vereinheitlichung (Map-Only Policy)

**Status:** ✅ IMPLEMENTED

### WHAT
Alle Attribute im `Ctx`, die bisher Single-Objekte sein konnten (`features`, `preds`), werden auf einheitliche **dict[str, …]**-Struktur umgestellt.

→ Einheitlicher Datenvertrag über alle Stages, kompatibel zu Tap/Inspect/Transform-Decorators.

### WHY
- Einheitlicher Ctx-Vertrag (keine Sonderfälle DF vs dict)
- Volle Kompatibilität mit Tap/Inspect-Decorators
- Zukunftssicher für parallele Feature-/Modell-Sichten (z.B. verschiedene Clustering-Runs)

### Implementation Checklist

- [x] **Ctx anpassen:**
  - `features: dict[str, pd.DataFrame] = field(default_factory=dict)`
  - `preds: dict[str, pd.Series] = field(default_factory=dict)`
- [x] **Default-Key definieren:**
  - Via keyword-args gesetzt, sonst `"default"`
- [x] **Erzeuger anpassen:**
  - `windowing()` → schreibt `features["default"] = df`
  - `local_clustering()` → schreibt `preds["default"] = series`
- [x] **Verbraucher anpassen:**
  - Alle Zugriffe auf `ctx.features` / `ctx.preds` → `ctx.features["default"]` / `ctx.preds["default"]`
  - `if ctx.features is None:` → `if not ctx.features:`
- [x] **Tests aktualisieren:**
  - Smoke-Test für Standard-Key `"cluster"` (78 Tests gesamt)
  - Leerer dict als Startzustand funktioniert
- [x] **ADR ergänzen:**
  - ADR-005 wurde mit Update 2025-12 aktualisiert (ctx.features statt ctx.windows)

**Referenz:** `local/Protokoll zu M6 Ctx-Struktur anpassen.md`

---

## 3️⃣ Visual Debugging & Inspection

**Status:** 🟡 PLANNING

### WHAT
Erweiterung der Debug- und Inspektionsmöglichkeiten während Pipeline-Durchläufen.

Die Funktionalität soll keine neuen Pipeline-Stages einführen, sondern optionale **Inspektoren** in `inspect.py` bündeln, um DataFrames visuell, interaktiv oder in Berichtsform prüfen zu können.

### 3.1 D-Tale – Externer Debug-Inspektor

**Ziel:** Temporäre visuelle Exploration von DataFrames oder Dicts von DataFrames direkt aus laufendem Code (z. B. innerhalb eines Tap-Aufrufs).

**Kerneigenschaft:**
- Startet lokalen Flask-Server (`localhost:40xxx`)
- Greift live auf DataFrame im Speicher zu (kein CSV-Dump)
- Zeigt interaktive Tabellen, Plots, Statistik
- Mehrere Sessions gleichzeitig möglich (z. B. für verschiedene Sensoren)

**Einsatzidee:**
- In `inspect.py` als `inspect_with_dtale(obj, name="features")`
- Optional über CLI-Flag `--inspect-dtale` oder Config-Key `debug.inspect_dtale`
- Öffnet Browserfenster; kein Einfluss auf Pipelinefluss

**Bewertung:**
- 🟢 Sehr nützlich für schnelle Pipeline-Debugs
- 🟡 Ressourcenverbrauch (lokaler Server) beachten
- 🔴 Keine automatisierte CI-Verwendung möglich

### 3.2 Lux – Inline-Inspektor (nur Interactive Mode)

**Ziel:** Schnellvisualisierung direkt in VS Code Interactive Window oder Jupyter-Kernel.

**Hinweise:**
- Funktioniert **nur**, wenn Code in einer Jupyter-ähnlichen Umgebung läuft (VS Code Interactive Window oder `.ipynb`)
- Keine Wirkung im klassischen Terminal/CLI-Run
- Minimaler Wrapper prüft Umgebung und gibt ggf. DataFrame normal aus

**Einsatzidee:**
- In `inspect.py` als `inspect_with_lux(df)`
- Kein persistenter Output – nur zur Laufzeit sichtbar

**Bewertung:**
- 🟢 Intuitiv für exploratives Debugging
- 🟡 Kaum relevant für automatisierte Runs
- 🔴 Abhängig von VS Code/Notebook-Kernel

### 3.3 EDA-Reports (Exploratory Data Analysis)

**Ziel:** Erzeugung reproduzierbarer Artefakte für Datenverständnis, Regression-Vergleiche und Pipeline-Dokumentation.

**Kandidaten:**
- `dataprep.eda` – schnell, übersichtlich, gute Default-Plots
- `ydata-profiling` – sehr detailliert, eher schwergewichtig
- `sweetviz` – schön für Vergleichsdaten (train/test)

**Einsatzidee:**
- In `inspect.py` als `write_eda_report(obj, outdir=".artifacts/eda", engine="dataprep")`
- Optional konfigurierbar über `debug.eda = true`
- Reports als HTML/PDF in Artefakten ablegen

**Bewertung:**
- 🟢 Reproduzierbar, dokumentierbar, CI-tauglich
- 🟢 Nützlich für Regressionsvergleiche (Datenprofil vor/nach Änderung)
- 🟡 Moderate Laufzeit (abhängig von Datengröße)

### 3.4 Rich Logging

**Ziel:** Schönes, strukturiertes Terminal-Logging mit Farben, Progress-Bars, Tabellen.

**Einsatzidee:**
- `rich.console` für Statusmeldungen
- `rich.progress` für Pipeline-Fortschritt (Stage-by-Stage)
- `rich.table` für Metriken-Ausgabe am Ende

**Bewertung:**
- 🟢 Verbessert UX erheblich
- 🟢 Kein Overhead, reine Terminal-Ausgabe
- 🟡 Logging-Framework sollte trotzdem parallel laufen (für Files/CI)

**Referenz:** `local/Protokoll zu M6 - Visual Debugging.md`

---

## Implementation Priority

**Hoch (M6.1):**
1. Ctx Map-Only Policy fertigstellen (Tests + ADR)
2. Pipeline Defaults Mechanismus implementieren

**Mittel (M6.2):**
3. Rich Logging einführen
4. D-Tale Debug-Inspektor (optional via Config)

**Niedrig (M6.3):**
5. EDA-Reports (nice-to-have für Dokumentation)
6. Lux Integration (nur für Interactive Mode)

---

**Referenzen:**
- `local/Protokoll_M6_Pipeline_Defaults.md`
- `local/Protokoll zu M6 Ctx-Struktur anpassen.md`
- `local/Protokoll zu M6 - Visual Debugging.md`
