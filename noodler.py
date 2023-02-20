from PyQt6.QtWidgets import QApplication,QLabel,QSlider,QVBoxLayout,QWidget
from PyQt6.QtCore import Qt
from PyQt6 import QtGui
import transcribe
from pytube import YouTube
import json
import librosa
import numpy
import os
import pyaudio
import time

MUSIC_PATH = "music"

class Window(QWidget):

    def __init__(self, transcriber):
        super().__init__()
        self.transcriber = transcriber 

        self.resize(300, 250)
        self.setWindowTitle("CodersLegacy")
 
        self.label = QLabel(self)
        self.label.move(130, 100)
 
        slider = QSlider(Qt.Orientation.Horizontal, self)
        slider.setGeometry(50,50, 500, 50)
        slider.setTickPosition(QSlider.TickPosition.NoTicks)
        slider.setMinimum(0)
        slider.setMaximum(10000)
        slider.valueChanged.connect(self.display)   
     
    def display(self):
        print(self.sender().value())
        self.label.setText("Value: "+str(self.sender().value()))
        self.label.adjustSize()  # Expands label size as numbers get larger

    def keyPressEvent(self, a0: QtGui.QKeyEvent) -> None:
        if transcriber.playing:
            transcriber.stop()
        else:
            transcriber.play()
        return super().keyPressEvent(a0)

def get_available_music():
    return [f for f in os.listdir(MUSIC_PATH) if os.path.isfile(os.path.join(MUSIC_PATH, f))]
 
print("\nWelcome to noodler.\n")
if not os.path.exists("music"):
    os.makedirs("music")
available_music = get_available_music()
print("Tracks available locally:\n")
for (i, file) in enumerate(available_music):
    print("{}) {}".format(i + 1, os.path.basename(file)))
print("")
track = input("Enter the URL of a YouTube video to transcribe, or select a song from above: ")
path = None
if track.isnumeric():
    index = int(track) - 1
    if index < 0 or index >= len(available_music):
        print("Invalid selection")
        exit()
    path = os.path.join(MUSIC_PATH, available_music[index])
else:
    path = YouTube(track).streams.filter(only_audio = True).first().download(output_path="music")
print("Downloaded music to " + path)
data, sampling_rate = librosa.load(path, sr=None, mono=False)
transcriber = transcribe.TranscribeContext(os.path.basename(path), data, sampling_rate)

app = QApplication([])
app.setStyle('macos')
window = Window(transcriber)
window.show()
app.exec()