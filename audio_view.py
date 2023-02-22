from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGraphicsScene,
    QGraphicsSceneMouseEvent,
    QGraphicsView,
    QInputDialog,
    QMainWindow,
    QLineEdit,
    QLabel,
    QWidget,
    QPushButton,
    QDockWidget,
    QBoxLayout,
    QGraphicsTransform,
    QGraphicsScale,
)
from PyQt6.QtCore import (
    Qt, 
    QTimer,
    QByteArray,
)
from PyQt6 import QtGui
import transcribe
from pytube import YouTube
import librosa
import os
import math
import threading
import transcribe

class AudioWaveformView(QGraphicsView):
    # audio_data must be mono
    def __init__(self, audio, *args, **kargs):
        super(AudioWaveformView, self).__init__(*args, **kargs)
        self.audio_waveform_scene = AudioWaveformScene(audio)
        self.setScene(self.audio_waveform_scene)
        self.audio = audio
        self.duration = librosa.get_duration(audio.data, sr=audio.sampling_rate)
        self.timestamp = 0.0
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.horizontalScrollBar().setValue(1)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.show()

    def zoom_in(self):
        self.audio_waveform_scene.zoom_in()

    def zoom_out(self):
        self.audio_waveform_scene.zoom_out()

class AudioWaveformScene(QGraphicsScene):
    # audio_data must be mono
    def __init__(self, audio, *args, **kargs):
        super(AudioWaveformScene, self).__init__(*args, **kargs)
        self.setBackgroundBrush(Qt.GlobalColor.gray)
        self.audio = audio
        self.total_height = 180
        self.waveform_height = 150
        self.scale = 1.0
        self.duration = librosa.get_duration(audio.data, sr=audio.sampling_rate)
        self.timestamp = 0.0
        self.waveform = self.create_waveform(1200, self.waveform_height, librosa.to_mono(audio.data))
        self.waveform.setY(30)
        self.timeline = self.create_timeline(1200, 30, self.duration)
        self.add_cursor_to_scene()
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

    def shift_loop(self, amount):
        loop_width = self.loop_end - self.loop_start
        if amount > 0:
            self.loop_end += amount
            if self.loop_end > self.duration:
                self.loop_end = self.duration
            self.loop_start = self.loop_end - loop_width
        else:
            self.loop_start += amount
            if self.loop_start < 0.0:
                self.loop_start = 0.0
            self.loop_end = self.loop_start + loop_width
        # should consolidate this
        self.audio.set_start(self.loop_start)
        self.audio.set_end(self.loop_end)
        self.update_loop()
        self.update_timestamp()

    def zoom_in(self):
        self.scale_waveform(self.scale * 1.2)

    def zoom_out(self):
        self.scale_waveform(self.scale / 1.2)

    def scale_waveform(self, scale):
        self.scale = scale
        if self.scale < 1.0:
            self.scale = 1.0
        scale_transform = QGraphicsScale()
        scale_transform.setXScale(self.scale)
        self.waveform.setTransformations([scale_transform])
        self.update_rect()

        if self.timeline != None:
            self.removeItem(self.timeline)
        self.timeline = self.create_timeline(self.width(), 30, self.duration)

        self.update_loop()
        self.update_timestamp()

    def update_rect(self):
        self.setSceneRect(0, 0, self.waveform.boundingRect().width() * self.scale, self.total_height)

    def update_timestamp(self) -> bool:
        timestamp = self.audio.current_timestamp
        self.timestamp_cursor.setPos(self.width() * timestamp / self.duration, 0.0)

    # should add at x = 0
    def add_cursor_to_scene(self):
        cursor_x = self.width() * self.timestamp / self.duration + 1
        cursor_height = self.total_height
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
        self.left_loop_rect.setRect(0, 30, loop_start_in_px, self.total_height - 30)
        self.right_loop_rect.setRect(loop_end_in_px, 30, self.width() - loop_end_in_px, self.total_height - 30)
        self.update_rect()

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

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        if self.setting_loop:
            timestamp = self.duration * event.scenePos().x() / self.width()
            if timestamp < self.loop_start:
                timestamp = self.loop_start
            self.loop_end = timestamp
            self.audio.set_end(self.loop_end)
            self.update_loop()
        # capture the move event for efficiency
        return None

    def create_waveform(self, width, height, audio_data):
        vertical_margin = 0
        effective_height = height - vertical_margin * 2
        chunks = int(len(audio_data) / 1000)
        chunk_pixel_width = float(width) / chunks
        chunk_sample_width = int(len(audio_data) / chunks)
        items = []
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
            items.append(self.addRect(chunk_pixel_start, max_line_start, chunk_pixel_width, max_line_height, Qt.GlobalColor.blue, Qt.GlobalColor.blue))
            # items.append(self.addRect(chunk_pixel_start, rms_line_start, chunk_pixel_width, rms_line_height, Qt.GlobalColor.darkBlue, Qt.GlobalColor.darkBlue))
        waveform = self.createItemGroup(items)
        return waveform

    def create_timeline(self, width, height, duration):
        line = self.addLine(0.0, height - 2, width, height - 2, Qt.GlobalColor.black)
        # handle case where no resolution works?
        # ms
        possible_resolutions = [10, 100, 1000, 5000, 20000, 600000, 300000]
        min_tick_spacing = 10
        ticks = [r for r in possible_resolutions if width * r / (duration * 1000) > min_tick_spacing]
        smaller_tick = ticks[0]
        bigger_tick = ticks[1]
        ms = 0
        while ms < duration * 1000:
            second = ms / 1000
            x = width * second / duration
            if ms % bigger_tick == 0:
                tick = self.addLine(x, 0, x, height - 2, Qt.GlobalColor.black)
                time_str = transcribe.seconds_to_time_str(second)
                font = QtGui.QFont("Courier New", 9)
                text = self.addText(time_str, font)
                text.setDefaultTextColor(Qt.GlobalColor.black)
                text.setPos(x, height - 28)
                text.setParentItem(line)
            else:
                tick = self.addLine(x, height - 6, x, height - 2, Qt.GlobalColor.black)
            tick.setParentItem(line)
            ms += smaller_tick
        return line

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