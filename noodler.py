from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGraphicsScene,
    QGraphicsSceneMouseEvent,
    QGraphicsView,
    QInputDialog,
    QMainWindow,
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
import math

MUSIC_PATH = "music"
TIMESTAMP_EVENT = 55555

class AudioWaveformScene(QGraphicsScene):
    # audio_data must be mono
    def __init__(self, audio, *args, **kargs):
        super(AudioWaveformScene, self).__init__(*args, **kargs)
        self.setBackgroundBrush(Qt.GlobalColor.gray)
        self.audio = audio
        self.duration = librosa.get_duration(audio.data, sr=audio.sampling_rate)
        self.timestamp = 0.0
        self.add_waveform_to_scene(1200, 150, librosa.to_mono(audio.data))
        self.add_cursor_to_scene()
        self.setSceneRect(0, 0, 1200, 150)
        self.timer = QTimer()
        self.timer.start(50)
        # ideally only do this when playing the music
        self.timer.timeout.connect(self.update_timestamp)

        self.loop_start = 0.0
        self.loop_end = self.duration
        self.left_loop_rect = None
        self.right_loop_rect = None
        self.add_loop_to_scene()
        self.setting_loop = False

    def update_timestamp(self) -> bool:
        timestamp = self.audio.current_timestamp
        self.timestamp_cursor.setPos(self.width() * timestamp / self.duration, 0.0)

    # should add at x = 0
    def add_cursor_to_scene(self):
        cursor_x = self.width() * self.timestamp / self.duration
        cursor_height = self.height()
        self.timestamp_cursor = self.addLine(cursor_x, 0, cursor_x, cursor_height, Qt.GlobalColor.red)

    def add_loop_to_scene(self):
        brush = QtGui.QBrush(QtGui.QColor(0, 0, 0, 100))
        pen = QtGui.QPen(QtGui.QColor(0, 0, 0, 100))
        self.left_loop_rect = self.addRect(0, 0, self.width(), self.height(), pen, brush)
        self.right_loop_rect = self.addRect(0, 0, self.width(), self.height(), pen, brush)
        self.update_loop()

    def update_loop(self):
        loop_start_in_px = self.width() * self.loop_start / self.duration
        loop_end_in_px = self.width() * self.loop_end / self.duration
        self.left_loop_rect.setRect(0, 0, loop_start_in_px, self.height())
        self.right_loop_rect.setRect(loop_end_in_px, 0, self.width() - loop_end_in_px, self.height())

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        self.audio.stop()
        timestamp = self.duration * event.scenePos().x() / self.width()
        self.setting_loop = True
        self.loop_start = timestamp
        self.loop_end = timestamp
        self.audio.set_start(self.loop_start)
        self.update_loop()
        return super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        self.setting_loop = False
        return super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self.setting_loop:
            timestamp = self.duration * event.scenePos().x() / self.width()
            if timestamp < self.loop_start:
                timestamp = self.loop_start
            self.loop_end = timestamp
            self.audio.set_end(self.loop_end)
            self.update_loop()
        return super().mouseMoveEvent(event)

    def add_waveform_to_scene(self, width, height, audio_data):
        vertical_margin = 0
        effective_height = height - vertical_margin * 2
        chunks = int(len(audio_data) / 5000)
        chunk_pixel_width = float(width) / chunks
        chunk_sample_width = int(len(audio_data) / chunks)
        for chunk in range(0, chunks):
            chunk_start = int(chunk * chunk_sample_width)
            chunk_end = int((chunk + 1) * chunk_sample_width)
            if chunk_start < 0:
                chunk_start = 0
            if chunk_end > len(audio_data):
                chunk_end = len(audio_data)
            chunk_data = audio_data[chunk_start:chunk_end]
            (max, rms) = self.max_and_rms(chunk_data)
            max_line_height = effective_height * max / 1.0
            max_line_start = vertical_margin + (effective_height - max_line_height) / 2
            rms_line_height = effective_height * rms / 1.0
            rms_line_start = vertical_margin + (effective_height - rms_line_height) / 2
            chunk_pixel_start = chunk * chunk_pixel_width
            self.addRect(chunk_pixel_start, max_line_start, chunk_pixel_width, max_line_height, Qt.GlobalColor.blue, Qt.GlobalColor.blue)
            self.addRect(chunk_pixel_start, rms_line_start, chunk_pixel_width, rms_line_height, Qt.GlobalColor.darkBlue, Qt.GlobalColor.darkBlue)

    def max_and_rms(self, samples):
        total = 0
        max = 0
        for sample in samples:
            total += sample * sample
            if sample > max:
                max = sample
        total /= len(samples)
        rms = math.sqrt(total)
        return (max, rms)


class AudioWaveformView(QGraphicsView):
    # audio_data must be mono
    def __init__(self, audio, *args, **kargs):
        super(AudioWaveformView, self).__init__(*args, **kargs)
        self.setScene(AudioWaveformScene(audio))
        self.audio = audio
        self.duration = librosa.get_duration(audio.data, sr=audio.sampling_rate)
        self.timestamp = 0.0
        self.setFixedHeight(154)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.show()

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.resize(800, 600)
        self.setWindowTitle("Noodler")

        fileMenu = self.menuBar().addMenu("File")
        openAction = fileMenu.addAction("Open...")
        openAction.triggered.connect(self.open)
        importAction = fileMenu.addAction("Import From YouTube...")
        importAction.triggered.connect(self.import_from_youtube)

    def open(self):
        (path, _) = QFileDialog.getOpenFileName(None, "Open Audio File", "music", "Audio Files (*.mp4)");
        self.load(path)

    def import_from_youtube(self):
        (url, _) = QInputDialog.getText(None, "Import From YouTube", "YouTube URL:")
        if not os.path.exists("music"):
            os.makedirs("music")
        path = YouTube(url).streams.filter(only_audio = True).first().download(output_path="music")
        self.load(path)

    def load(self, path):
        data, sampling_rate = librosa.load(path, sr=None, mono=False)
        self.audio = transcribe.TranscribeContext(os.path.basename(path), data, sampling_rate, lambda: 0)
        self.audio_waveform = AudioWaveformView(self.audio, self)
        self.audio_waveform.move(100, 100)
        self.setCentralWidget(self.audio_waveform)

    def keyPressEvent(self, a0: QtGui.QKeyEvent) -> None:
        if self.audio.playing:
            self.audio.stop()
        else:
            self.audio.play()
        return super().keyPressEvent(a0)
 
app = QApplication([])
app.setStyle('macos')
window = MainWindow()
window.show()
app.exec()