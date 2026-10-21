# Videos einer Aufnahme zusammenfügen

Aus dem Projektverzeichnis ausführen (Ordnerpfade mit Leerzeichen in Anführungszeichen):

```powershell
python video_postprocessing/merge_videos.py "Z:\n2023_odor_related_behavior\2026_sick_behavior\raw\c3\habituation\20261020_100930_030051_mice_c3_habituation_home" top
```
Für die andere Kamera `top` durch `side` ersetzen. Benötigt werden `session.json`,
`top_frames.csv` bzw. `side_frames.csv` und alle zugehörigen AVI-Segmente im Ordner.
Das Format entspricht `optimized_recording/run_single_module.py`.
Die Aufnahme muss beendet sein. Bei fehlender, unlesbarer oder unvollstaendiger
`session.json` (z. B. Status `recording` nach Stromausfall) greift automatisch
der CSV-Fallback: Segmente und Frame-Anzahlen kommen aus `top_frames.csv`
bzw. `side_frames.csv`, zugeordnet zu `top_000001.avi` usw. Dafuer ist kein
zusaetzlicher Parameter erforderlich. Ohne gueltige FPS in der JSON werden
die FPS aus den AVI-Dateien gelesen und auf Uebereinstimmung geprueft.
Die CSV-Zeitstempel bleiben die Grundlage fuer die zeitliche Anordnung.
Beschaedigte Videos oder Abweichungen zwischen CSV und dekodierbaren Frames
fuehren weiterhin zum Abbruch. Der Fallback repariert keine Videodateien.
Da auch die CSV gepuffert geschrieben wird, koennen bei Stromausfall ihre
letzten Eintraege fehlen.

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
erfunden. Ohne DLC-Konfiguration bleiben alle F?llbilder schwarz.

## Optional: Segment-Endbilder mit DeepLabCut pr?fen

```powershell
python video_postprocessing/merge_videos.py "Z:\n2023_odor_related_behavior\2026_sick_behavior\raw\c3\baseline\20261021_100830_142931_mice_c3_baseline_home" top --dlc-config "C:\DLC-Projekt\config.yaml" --dlc-likelihood 0.6
```

Im Python-Environment m?ssen das trainierte DeepLabCut-Netzwerk sowie pandas
und PyTables verf?gbar sein. Pro Segment wird das letzte Bild als Ein-Frame-AVI
(MJPG) gespeichert und mit `deeplabcut.analyze_videos(..., auto_track=True)`
analysiert. Die H5-Auswertung unterst?tzt Single- und Multi-Animal-Spalten.
Mindestens ein Punkt mit endlichen Koordinaten und einer Likelihood strikt
?ber dem Grenzwert gen?gt. Das urspr?ngliche Endbild f?llt dann die L?cke zum
n?chsten Segment. Ohne einen solchen Punkt bleibt diese L?cke schwarz.
L?cken innerhalb eines Segments bleiben immer schwarz. Die Markierungen
erscheinen ausschlie?lich auf den Kontrollbildern.

Unter `CAMERA_dlc_control/run_.../` entstehen pro Lauf:

- `accepted/`: Endbilder mit eingezeichneten Punkten und Likelihoods.
- `rejected/`: Endbilder ohne ausreichend sichere Vorhersage.
- `analysis/SEGMENT/`: Ein-Frame-AVI, DLC-Ergebnisse und `decision.json` mit
  Konfiguration, Grenzwert, Vorhersagen und Anzahl tats?chlich erg?nzter Frames.

Mit `--dlc-control-dir` l?sst sich das Stammverzeichnis ?ndern. Jeder Lauf hat
einen eigenen Ordner; Ergebnisse ?lterer L?ufe werden nicht wiederverwendet.
Auch das letzte Segment wird gepr?ft, erg?nzt aber keine Zeit nach Aufnahmeende.
`accepted` bedeutet f?r die F?llung geeignet; bei fehlender anschlie?ender L?cke
ist `filled_frames` in der Entscheidungsdatei null. Die Zusammenfassung z?hlt
`held_frames` und `black_frames` getrennt.

Fehlende, mehrdeutige oder fehlerhafte H5-Ergebnisse f?hren zum Abbruch, nicht
zu einer Einstufung als ?keine Maus?. Eine niedrige Likelihood bedeutet lediglich,
dass keine ausreichend sichere Erkennung vorliegt. Bei Multi-Animal-Projekten
muss die verwendete DLC-Version mit ihrer Tracking-Konfiguration H5-Ergebnisse
auch f?r ein einzelnes Frame erzeugen k?nnen; zeitliche Track-Filter k?nnen dies
verhindern. Dieser Netzwerkschritt ist mit dem konkreten Projekt zu pr?fen.
Die bisherige automatisierte Pr?fung verwendet simulierte DLC-Inferenz und
reale H5-, AVI- und MP4-Dateien.

DLC-Aufruf und H5-Ausgabe: [offizielle DLC-Dokumentation](https://deeplabcut.github.io/DeepLabCut/docs/standardDeepLabCut_UserGuide).
