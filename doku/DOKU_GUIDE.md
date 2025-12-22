# Dokumentations-Guide

Schneller Einstieg in die Projektdokumentation.

---

## 📁 Struktur-Überblick

| Kategorie | Inhalt | Einstiegspunkt |
|-----------|--------|----------------|
| **architecture/** | Architektur-Entscheidungen & Verträge | `ADRs.md` |
| **specifications/** | Technische Specs pro Milestone | `M3_Features.md` |
| **protocols/** | Chronologischer Projektverlauf | `Decision_Log.md` |
| **roadmap/** | Milestones & GitHub Issue-Templates | `Milestones.md` |
| **references/** | Externe Referenzen (z.B. SensorLogger) | `SensorLogger.md` |

---

## 🎯 Schnelleinstieg

**Projektverlauf verstehen?**
→ `protocols/Decision_Log.md` - Chronologische Übersicht aller Sessions

**Architektur verstehen?**
→ `architecture/ADRs.md` - Architektur-Entscheidungen
→ `architecture/Contracts.md` - Runner-Verträge

**Implementierung verstehen?**
→ `specifications/` - Technische Details pro Milestone
→ Beispiel: `M3_Features.md` für Feature Engineering

**Roadmap & Planung?**
→ `roadmap/Milestones.md` - Milestone-Übersicht

---

## 🔄 Für Contributors

<details>
<summary>Pflege-Regeln (klick zum Ausklappen)</summary>

### Decision_Log.md
- **Append-Only** (unten anhängen)
- Pro Session: Datum, Entscheidungen, Outcome, Referenz

### Specifications (M2, M3, M4, ...)
- **Aktualisieren** (immer neuester Stand)
- Header pflegen: `Last Updated`, `Status`

### ADRs.md
- **Append-Only** (neue ADRs unten)
- Alte ADRs nie löschen, nur Status: "Superseded"

### Status-Labels
- 🟡 `PLANNING` - In Planung
- ✅ `IMPLEMENTED` - Fertig
- 🔴 `DEPRECATED` - Veraltet

### Wichtig
Git ist das Versionssystem - keine Versionsnummern in Dateinamen!

</details>
