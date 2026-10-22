# Videos einer Aufnahme zusammenfügen

Im Projektverzeichnis ausführen. Die Aufnahme muss beendet sein. Benötigt werden
`session.json`, `top_frames.csv` bzw. `side_frames.csv` und die zugehörigen AVI-Fragmente.
Die Originalvideos und das trainierte DLC-Projekt werden nicht verändert.

## Vorliegende Aufnahme mit geprüften Entscheidungen

Die bereits geprüfte JSON-Datei dieser Aufnahme kann ohne erneute DLC-Inferenz verwendet werden:

```powershell
python -B video_postprocessing/merge_videos.py "Z:\n2023_odor_related_behavior\2026_sick_behavior\raw\c3\baseline\20261021_100830_142931_mice_c3_baseline_home" top --gap-decisions "E:\Fabi_Setup\merge_testing\gap_decisions_reviewed.json"
```

Standardziel ist der neue Unterordner `top_merge` im Aufnahmeordner. Darin liegen
`top_merged.mp4` und alle Kontrolldateien. Für die andere Kamera `top` durch `side` ersetzen.
Mit `--destination "E:\Fabi_Setup\merge_testing\neuer_testlauf"` kann ein anderes
Zielverzeichnis gewählt werden. Bestehende Videos und `control`-Ordner werden niemals
überschrieben; für einen weiteren Lauf ein neues Ziel verwenden. Nach einem Abbruch
bleiben die bisherigen Kontrolldateien und `status.json` zur Fehlersuche erhalten.

`--output` erlaubt einen eigenen MP4-Dateinamen innerhalb des Zielordners. Wird nur
`--output` angegeben, ist dessen übergeordneter Ordner das Ziel für alle Ergebnisse.

## Füllregeln und Zeitachse

- **Kurze Lücken innerhalb eines Fragments:** Das letzte dekodierte Originalbild wird
  wiederholt, wenn die fehlende Ausgabezeit höchstens **0,1 Sekunden** beträgt
  (bei 30 FPS bis zu drei Füllbilder). Das verhindert schwarze Blitze durch Zeitstempel-Jitter.
  Mit `--short-gap-seconds 0.05` lässt sich die Grenze ändern; `0` deaktiviert die Wiederholung.
- **Längere Lücken innerhalb eines Fragments:** schwarze Bilder.
- **Lücken zwischen Fragmenten:** Bei positiver DLC-Erkennung bzw. JSON-Entscheidung
  `hold` wird das letzte Originalbild des vorherigen Fragments wiederholt. Andernfalls
  werden schwarze Bilder eingesetzt. Kurze Fragmentgrenzen werden ebenfalls nach
  dieser Anwesenheitsentscheidung behandelt, nicht automatisch gehalten.
- **DLC-Fehler:** schwarze Bilder für die betroffene Fragmentlücke; Warnung und
  Fehlertext werden gespeichert, die Verarbeitung läuft weiter. Das gilt auch für
  fehlende DLC-Abhängigkeiten und fehlende, mehrdeutige oder ungültige H5-Ergebnisse.
- **Nahtlose Fragmentgrenzen:** keine Füllbilder. Nach dem letzten Fragment wird
  keine zusätzliche Zeit ergänzt.

Die CSV-Spalte `host_monotonic_ns` bestimmt die Position jedes Bildes auf einem
konstanten FPS-Raster. Die Ausgabe beginnt mit dem ersten gespeicherten Bild.
Wenn mehrere Originalbilder auf dieselbe Position fallen, bleibt das erste dort;
weitere werden nur in der Ausgabe ausgelassen und gezählt. Alle Originalbilder
werden trotzdem dekodiert und geprüft. Die Zeitachse wird nicht verschoben.
Das tatsächliche letzte Quellbild bleibt auch bei solchen Kollisionen das Bild für
anschließende Wiederholungen und für `last.png`.

Die Zeitauflösung ist ein Frame. Host-Zeitstempel messen den Abruf, nicht die
Belichtung. Schwarze Bilder bzw. Wiederholungen rekonstruieren keine unbeobachtete
Bewegung während einer Aufnahmepause.

## Kontrolle im Zielordner

```text
top_merge/
  top_merged.mp4
  summary.json
  status.json
  ffmpeg.log
  control/
    gaps.jsonl
    top_000001/
      first.png
      last.png
      decision.json
    top_000002/
      first.png
      last.png
      decision.json
    dlc/                         # bei tatsächlicher DLC-Inferenz für Lücken
      top_000001/
        last.avi
        prediction.png
        decision.json
        ... DLC-Ergebnisse ...
```

`first.png` und `last.png` zeigen die tatsächlichen ersten und letzten dekodierten
Quellbilder jedes Fragments ohne Markierungen. `decision.json` enthält die
Quellzeitstempel, Frame-Anzahlen, ausgelassene Kollisionen, interne Füllbildzahlen
und die Entscheidung zur folgenden Fragmentlücke einschließlich Grund,
Füllbildanzahl und gegebenenfalls DLC-Fehlertext. Auch das letzte Fragment erhält
Kontrollbilder und den Grund `end_of_recording`.

`gaps.jsonl` enthält pro interner Lücke und pro Fragmentgrenze einen JSON-Datensatz:
Ausgabestartframe (nullbasiert), Länge, `hold`/`black`/`none` und Grund. Zusammen mit
`first.png` des nächsten Fragments lässt sich jede Grenze kontrollieren.
`fill_seconds` ist die tatsächlich ergänzte Zeit; `source_interval_seconds` an
Fragmentgrenzen ist der Zeitabstand der beiden Quellbilder inklusive eines
regulären Frame-Intervalls und kann deshalb um ungefähr 1/FPS größer sein.
`summary.json` zählt schwarze, gehaltene und wegen Kollision ausgelassene Bilder;
`status.json` unterscheidet `running`, `failed` und `complete`.

## Neue Entscheidungen mit DeepLabCut erzeugen

```powershell
python -B video_postprocessing/merge_videos.py "Z:\n2023_odor_related_behavior\2026_sick_behavior\raw\c3\baseline\20261021_100830_142931_mice_c3_baseline_home" top --dlc-config "E:\Fabi_Setup\In_Soundchamber\multi_animal\multi_animal-Fabi-2026-10-14\config.yaml" --dlc-shuffle 2 --dlc-likelihood 0.6 --destination "E:\Fabi_Setup\merge_testing\neuer_dlc_lauf"
```

DLC wird nur für Fragmentenden mit anschließender Lücke geladen. Die Eingabe ist
jeweils ein Ein-Frame-MJPG-AVI im Zielordner. Der Aufruf verwendet
`auto_track=False, save_as_df=True, batch_size=1`: Anwesenheitserkennung benötigt
kein zeitliches Tracking. Single- und Multi-Animal-H5-Spalten werden unterstützt.
Mindestens ein Punkt mit endlichen Koordinaten innerhalb des Bildes und einer
Likelihood **strikt über** dem Grenzwert führt zu `hold`.

Shuffle 2 ist hier Standard, weil er die beiden Beispielgrenzen korrekt erkannte;
Shuffle 1 verfehlte in diesem Projekt auch sichtbare Mäuse. Andere Projekte können
`--dlc-shuffle 1` benötigen. Die Regel kann Fehlalarme auf dunkler Einstreu liefern.
Niedrige Likelihood beweist keine Abwesenheit, insbesondere bei verdeckten Mäusen.
Deshalb die Kontrollbilder prüfen oder eine geprüfte JSON-Datei verwenden.
DLC-Fehler führen wie oben beschrieben zu Schwarz, nicht zur Annahme einer Maus.
Dateisystemfehler beim Speichern der Kontrollen und defekte Quellvideos bleiben
harte Fehler, damit keine unvollständig dokumentierte oder erfundene Aufnahme entsteht.

`--gap-decisions` und `--dlc-config` sind Alternativen. Eine einfache JSON-Datei
ordnet jedem AVI-Dateinamen `black` oder `hold` zu. Das geprüfte Format mit
`source_folder`, `camera`, `timeline_sha256` und `decisions` wird ebenfalls
unterstützt und vor dem Start gegen die Aufnahme geprüft. Ohne beide Optionen
bleiben Fragmentlücken schwarz; kurze interne Lücken werden weiterhin gehalten.

DLC-Aufruf: [offizielle API-Dokumentation](https://deeplabcut.github.io/DeepLabCut/dev/latest-release/reference/deeplabcut/pose_estimation_pytorch/apis/videos/).

## Abhängigkeiten und Prüfungen

`python -m pip install numpy opencv-python` sowie FFmpeg mit `libx264` im PATH.
Alternativ `--ffmpeg "C:\Pfad\ffmpeg.exe"`. Für DLC zusätzlich eine passende
DeepLabCut-Installation einschließlich pandas und PyTables sowie ein trainiertes Modell.
Python 3.11 oder neuer wird für SHA256-Prüfungen gebundener JSON-Dateien benötigt.

Bei unvollständiger oder ungültiger `session.json` werden Fragmente und
Frame-Anzahlen aus der CSV gelesen. Fehlende FPS werden aus den AVI-Dateien
ermittelt und auf übereinstimmung geprüft. Die CSV-Zeitstempel bleiben maßgeblich.
Fehlende Fragmente, widersprüchliche Indizes/Frame-Anzahlen und Dekodierfehler
führen zum Abbruch; der Fallback repariert keine Quelldateien.

H.264 mit `--crf 18` ist verlustbehaftet und verwendet YUV420. Die Original-AVIs
für quantitative Analysen aufbewahren. Verarbeitung erfolgt speichersparend;
beim abschließenden Kopieren werden vorübergehend zwei Ausgabedateien benötigt.

Regressionstests (synthetische Videos; keine echten Quellen ändern):

```powershell
python -B -m unittest video_postprocessing.test_merge_videos
```
