# Untergrundklassifizierung

Hier entsteht zukünftig ein Projekt zur Untergrundklassifizierung beim Radfahren.

##UPDATE:

### Aktueller Stand
- Grundgerüst der Pipeline steht: Stages (Ingest → Select → Preprocess → Features → Classify → Export) sind implementiert.
- Datenfluss läuft über ein zentrales, unveränderliches `Ctx`-Objekt.
- Erste Module (`ingest`, `select`) sind funktional, andere Stages aktuell noch Platzhalter.
- Konfiguration erfolgt über `config.json`, einfache Validierung ist eingebaut.

### Nächste Schritte
- Ausbau von **Preprocessing** (Zeitindex, Resampling, Cleaning).
- Einführung von **Testing** (pytest) für zentrale Bausteine.
- Implementierung erster **Features** und Basisklassifikation.
- **Export** von Ergebnissen und Artefakten.


