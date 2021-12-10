

# Modell Installation
- Für die Identifikation von Tabellen und Bildern wird die Library MMDetection [1]   verwendet.
- Diese ist bisher nur mit Linux und OS kompatibel.
- Aufgrund von komplexen Abhängigkeiten innerhalb des Moduls muss über einen mächtigeren Packet-Manager die Library installiert werden.
- Dies geschieht über die Library MIM.
- Hierfür einfach den nachfolgenden Befehlt eingeben.
> pip install openmim
- Anschließend kann mit dieser die Library installiert werden.
> mim install mmcv

- Für das Erkennen des Typs eines Wortes wird Spacy verwendet.
- Diese benötigt nach der Installation der Hauptbibliothek eine zusätzliche Installation des verwendeten Modells.
- Hierfür muss in der Konsole der folgende Befehl eingegeben werden.
> python -m spacy download en_core_web_sm


[1] https://github.com/open-mmlab/mmdetection/blob/master/docs/get_started.md