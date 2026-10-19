# Videos einer Aufnahme zusammenfügen

Aus dem Projektverzeichnis ausführen (Ordnerpfade mit Leerzeichen in Anführungszeichen):

```powershell
python video_postprocessing/merge_videos.py "Z:\n2023_odor_related_behavior\2026_sick_behavior\raw\c2\sick\20261015_101348_332921_mice_c2_sick_stim" to
Für die andere Kamera `top` durch `side` ersetzen. Benötigt werden `session.json`,
`top_frames.csv` bzw. `side_frames.csv` und alle zugehörigen AVI-Segmente im Ordner.
Das Format entspricht `optimized_recording/run_single_module.py`.
Die Aufnahme muss beendet sein (`status: stopped`).

Abhängigkeiten: `python -m pip install numpy opencv-python` sowie FFmpeg mit
`libx264` im PATH. Alternativ `--ffmpeg "C:\Pfad\ffmpeg.exe"` angeben.

Das Ergebnis heißt `top_merged.mp4` bzw. `side_merged.mp4`. Mit
`--output "C:\Ziel\aufnahme.mp4"` lässt sich ein anderes Ziel wählen.
Vorhandene Ausgaben werden nicht überschrieben; Originaldateien bleiben erhalten.

Die FPS kommen aus der JSON-Konfiguration. Die CSV-Zeitstempel
`host_monotonic_ns` bestimmen die Position der Bilder auf einem konstanten
Frame-Raster. Freie Positionen werden schwarz gefüllt, auch innerhalb eines
Segments. Die Ausgabe beginnt beim ersten gespeicherten Frame und endet beim
letzten. Pausen davor/danach werden nicht ergänzt: `elapsed_seconds` enthält
auch Initialisierung/Aufräumen und liefert dafür keine zuverlässigen Grenzen.
Die Zeitauflösung ist ein Frame; Host-Zeitstempel messen den Abruf, nicht die
Belichtung. Bei Zeitstempel-Jitter werden kollidierende Bilder auf die nächste
freie Position verschoben, damit kein Originalframe verloren geht. Dadurch
kann die Ausgabe etwas länger werden; die Zusammenfassung zählt solche Bilder.
Kamera-Ticks werden ohne bekannte Tick-Frequenz nicht als Sekunden interpretiert.

H.264 komprimiert schwarze Abschnitte sehr gut. Trotzdem wird jedes Ausgabeframe
encodiert; lange Pausen benötigen entsprechend Rechenzeit. Die Verarbeitung
lädt nicht die ganze Aufnahme in den RAM. Die Standardeinstellung `--crf 18`
ist verlustbehaftet und konvertiert nach YUV420; die Originalvideos daher für
quantitative Bildanalysen aufbewahren. Während der abschließenden Kopie wird
vorübergehend Platz für zwei Ausgabedateien benötigt.

Fehlende Videos, inkonsistente CSV-Indizes/Frame-Anzahlen und Decoderfehler
führen zum Abbruch. Es wird kein Ersatz für fehlende/defekte Quelldateien
erfunden. `filler_frame()` ist die Erweiterungsstelle für eine spätere Logik;
aktuell gibt es ausschließlich schwarze Füllbilder, keine Schlaferkennung.
