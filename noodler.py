from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGraphicsScene,
    QGraphicsView,
    QInputDialog,
    QMainWindow,
    QWidget,
    QBoxLayout,
)
from PyQt6.QtCore import (
    Qt, 
    QTimer,
)
from PyQt6 import QtGui
import transcribe
from pytube import YouTube
import librosa
import os
import audio_view

MUSIC_PATH = "music"

class MainView(QWidget):
    def __init__(self, audio, *args, **kargs):
        super(MainView, self).__init__(*args, **kargs)
        self.audio_view = audio_view.AudioWaveformView(audio, self)
        layout = QBoxLayout(QBoxLayout.Direction.Down)
        layout.addWidget(self.audio_view)
        self.setLayout(layout)

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.main_view = None
        self.audio = None
        self.key_pressed = dict()

        self.resize(800, 600)
        self.setWindowTitle("Noodler")

        fileMenu = self.menuBar().addMenu("File")
        openAction = fileMenu.addAction("Open...", QtGui.QKeySequence.StandardKey.Open)
        openAction.triggered.connect(self.open)
        importAction = fileMenu.addAction("Import From YouTube...", QtGui.QKeySequence("Ctrl+Y"))
        importAction.triggered.connect(self.import_from_youtube)

        viewMenu = self.menuBar().addMenu("View")
        self.zoomInAction = viewMenu.addAction("Zoom In", QtGui.QKeySequence.StandardKey.ZoomIn)
        self.zoomOutAction = viewMenu.addAction("Zoom Out", QtGui.QKeySequence.StandardKey.ZoomOut)

        toolsMenu = self.menuBar().addMenu("Tools")
        setPlaybackRateAction = toolsMenu.addAction("Set Playback Rate", QtGui.QKeySequence("Ctrl+R"))
        setPlaybackRateAction.triggered.connect(self.set_playback_rate)

        self.timer = QTimer()
        self.timer.start(15)
        self.timer.timeout.connect(self.handle_key_presses)

    def is_key_pressed(self, key):
        return key in self.key_pressed and self.key_pressed[key]

    def handle_key_presses(self):
        if self.audio != None:
            if self.is_key_pressed(Qt.Key.Key_D) and self.audio.current_timestamp < self.audio.end_timestamp:
                if self.is_key_pressed(Qt.Key.Key_Shift):
                    self.audio.current_timestamp += 0.5
                else:
                    self.audio.current_timestamp += 0.05
            if self.is_key_pressed(Qt.Key.Key_A) and self.audio.current_timestamp > self.audio.start_timestamp:
                if self.is_key_pressed(Qt.Key.Key_Shift):
                    self.audio.current_timestamp -= 0.5
                else:
                    self.audio.current_timestamp -= 0.05

        if self.main_view != None:
            if self.is_key_pressed(Qt.Key.Key_E):
                self.main_view.audio_view.audio_waveform_scene.shift_loop(0.05)
            if self.is_key_pressed(Qt.Key.Key_Q):
                self.main_view.audio_view.audio_waveform_scene.shift_loop(-0.05)

    def open(self):
        (path, result) = QFileDialog.getOpenFileName(None, "Open Audio File", "music", "Audio Files (*.mp4)");
        if not result:
            return
        self.load(path)

    def import_from_youtube(self):
        (url, result) = QInputDialog.getText(None, "Import From YouTube", "YouTube URL:")
        if not result:
            return
        if not os.path.exists("music"):
            os.makedirs("music")
        path = YouTube(url).streams.filter(only_audio = True).first().download(output_path="music")
        self.load(path)

    def load(self, path):
        data, sampling_rate = librosa.load(path, sr=None, mono=False)
        self.audio = transcribe.TranscribeContext(os.path.basename(path), data, sampling_rate, lambda: 0)
        self.main_view = MainView(self.audio, self)
        self.zoomInAction.triggered.connect(self.main_view.audio_view.zoom_in)
        self.zoomOutAction.triggered.connect(self.main_view.audio_view.zoom_out)
        self.setCentralWidget(self.main_view)

    def set_playback_rate(self):
        (rate, _) = QInputDialog.getDouble(None, "Set Playback Rate", "Rate", value=1.0)
        # todo: handle the waiting period gracefully
        self.audio.set_rate(rate)

    def keyReleaseEvent(self, a0: QtGui.QKeyEvent) -> None:
        self.key_pressed[a0.key()] = False 
        return super().keyReleaseEvent(a0)

    def keyPressEvent(self, a0: QtGui.QKeyEvent) -> None:
        self.key_pressed[a0.key()] = True
        # bad
        if self.audio == None:
            return super().keyPressEvent(a0)
        if a0.key() == Qt.Key.Key_Space:
            if self.audio.playing:
                self.audio.stop()
            else:
                self.audio.play()
        return None
 
app = QApplication([])
app.setStyle('macos')
window = MainWindow()
window.show()
app.exec()