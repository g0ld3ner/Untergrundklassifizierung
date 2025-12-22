# System Validierung & Quality Check: Untergrundklassifizierung

**Datum:** 19.12.2025
**Projekt:** Untergrundklassifizierung (Fahrrad-Sensordaten)
**Fokus:** Preprocessing & Feature Engineering Review

---

## 1. Executive Summary (Vogelperspektive)
Die technische Pipeline (Code-Integrität, Signalverarbeitungs-Logik) ist **hervorragend strukturiert** und folgt industriellen Best Practices. Von der Ingestierung bis zum Feature-Engineering wurden keine logischen Fehler gefunden, welche die Daten zerstören würden.

Das Kernproblem der bisherigen unbefriedigenden Ergebnisse liegt **nicht im Code**, sondern in der **physikalischen Signalkette**. Die Montage des Sensors am Rücken des Fahrers fungiert als massiver Tiefpassfilter. Das Resultat ist ein extrem niedriges Signal-Rausch-Verhältnis (SNR), bei dem die Nutzsignale (Untergrundvibrationen) unter die Wahrnehmungsschwelle sinken oder von Störsignalen (Tretbewegungen des Fahrers) maskiert werden.

---

## 2. Detaillierte Befunde (Stage-by-Stage)

### A. Preprocessing (Integrität & Filterung)
*   **Zeitstempel & Synchronisation:** Die Ausrichtung auf UTC-Nanosekunden und das Resampling mit `origin="epoch"` sind exzellent gelöst. Die Synchronität zwischen IMU und GPS ist mathematisch garantiert.
*   **Filterung:** Die Verwendung von Zero-Phase Butterworth Filtern (`sosfiltfilt`) ist korrekt. Der Anti-Aliasing-Schutz vor dem Resampling ist vorhanden und wirksam.
*   **NaN-Strategie:** Das aktuelle `drop`-Verfahren ist riskant (Potenzial für Jitter). Empfehlung: Bei schlechter Datenqualität auf Interpolation umstellen.

### B. Feature Engineering (Normalisierung & Metrik)
*   **V-Normalisierung:** Der Ansatz, einen Exponenten $n$ für $Vib \propto v^n$ dynamisch zu lernen, ist mathematisch brillant, scheitert aber aktuell an der Datenqualität.
*   **Der "Elephant in the Room":** Ein beobachteter **$R^2$ Score von nahezu 0** bei der Geschwindigkeits-Regression beweist, dass die gemessene Vibration nicht mehr mit der Fahrphysik korreliert.
*   **Ursachenanalyse:** Die Dominanz von Tretbewegungen (1.0 - 1.5 Hz) im Beschleunigungssignal maskiert die echten Untergrundvibrationen. Der 2Hz-Hochpass ist hier das kritische Trennelement.

---

## 3. Identifizierte Risiken & Limitationen

1.  **Mounting (Körper-Dämpfung):** Das Handy im Trikot filtert hochfrequente Signaturen (Asphalt-Sirren, feiner Schotter) fast vollständig weg.
2.  **SNR (Signal-to-Noise Ratio):** Das verbleibende Signal am Rücken ist so leise, dass es vom Eigenrauschen des Sensors und der Biomechanik des Fahrers überlagert wird.
3.  **Feature-Blindheit:** Klassische Zeitbereichs-Features (RMS, STD) erfassen nur die Gesamtenergie. Diese ist am Rücken nicht mehr diskriminativ genug für verschiedene Untergründe.

---

## 4. Empfehlungen & Ausblick (Roadmap)

### Kurzfristig (Parameter-Tuning):
*   **Hochpass-Anpassung:** Experimentieren mit Cutoff-Frequenzen von **3.5 - 5.0 Hz**, um das Tret-Wackeln des Oberkörpers radikal zu eliminieren.
*   **ZCR-Validierung:** Überprüfung, ob die Zero-Crossing-Rate nach dem Filter noch plausible Werte (> 10Hz) liefert oder nur noch Rauschen misst.

### Mittelfristig (Feature-Evolution):
*   **Spektrale Bänder (PSD Bins):** Aufteilung der Energie in Bänder (z.B. 4-12Hz, 12-25Hz, 25-50Hz). Verhältnisse dieser Bänder zueinander (Spectral Ratios) sind robuster gegen absolute Dämpfung.
*   **Entropie-Features:** Messung der Signal-Chaos-Struktur statt der Amplitude.

### Langfristig (Systematik):
*   **Hardware-Mounting:** Testmessung mit Sensor am Fahrradrahmen/Lenker zur Gewinnung eines "Golden Datasets" (Referenz für maximal mögliche Signalqualität).
*   **Deep Learning:** Übergang zu 1D-CNNs auf Rohdaten, falls manuelle Features die komplexen Dämpfungs-Muster des Körpers nicht auflösen können.

---

**Abschlussurteil:**
Die Pipeline ist **Ready for MVP**. Der Fokus sollte nun von der Code-Entwicklung hin zur **experimentellen Parameter-Optimierung** und **Mounting-Tests** verschoben werden.
