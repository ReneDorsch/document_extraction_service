# Masterarbeit


# Requirements
Die notwendigen Requirements können über folgenden Befehl in der Konsole heruntergeladen und gebaut werden.

```commandline
pip install openmim
mim install mmdet
pip install -U -r requirments.txt
```
 Für weiterführende Informationen zu der Installation steht die Datei INSTALLATION.md zur Verfügung.  

# Verwendung
Um die Pipeline zu verwenden muss zunächst das Modell für das Named Entity Recognition heruntergeladen [1] und in 
einen 
Ordner /models/NamedEntityRecognitionModels abgespeichert werden. 
Falls ein anderer Speicherort gewählt wird muss in dem Modul B_Textanalyzes in der Datei
 settings.py der Pfad angepasst werden.
Zusätzlich wird das Modell en_core_web_sm benötigt. 
Dieses kann über folgenden Befehl heruntergeladen werden: 
python -m spacy download en_core_web_sm [3]


Im Modul C_KontextAnalyzes kann über die Datei settings.py das Question Answering Modul ausgetauscht werden. 
Hierfür kann ein beliebiges QA Modul aus HuggingFace [2] genutzt werden.
Dabei muss nur der Name des Moduls ausgetauscht werden. 

Um die einzelnen Module zu verwenden, muss aktuell noch in der Datei run.py der jeweilige markierte Teilbereich 
aktiviert sein. 

[1] https://faubox.rrze.uni-erlangen.de/getlink/fiA9jKR4c1vMCSJCEfdcbz8b/NamedEntityRecognitionModels

[2] https://huggingface.co/models

[3] https://spacy.io/models/en