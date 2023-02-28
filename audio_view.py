from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsScene,
    QGraphicsSceneMouseEvent,
    QGraphicsView,
    QGraphicsScale,
)
from PyQt6.QtCore import (
    Qt, 
    QTimer,
)
from PyQt6 import QtGui
import librosa
import math
import audio
import utils

class AudioWaveformView(QGraphicsView):
    # audio_data must be mono
    def __init__(self, audio_data, audio_player, on_loop_change, *args, **kargs):
        super(AudioWaveformView, self).__init__(*args, **kargs)
        self.audio_player = audio_player

        self.audio_waveform_scene = AudioWaveformScene(audio_data, audio_player, on_loop_change)
        self.setScene(self.audio_waveform_scene)

        self.setFrameShape(QFrame.Shape.NoFrame)
        self.horizontalScrollBar().setValue(1)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.show()

        self.dragging = False
        self.dragging_initial_mouse_x = 0.0
        self.dragging_initial_scroll_x = 0.0

    def zoom_in(self):
        self.zoom(1.2)

    def zoom_out(self):
        self.zoom(1 / 1.2)

    def zoom(self, factor):
        current_center = self.horizontalScrollBar().value() + self.width() / 2
        current_width = self.audio_waveform_scene.width()
        self.audio_waveform_scene.zoom(factor)
        new_width = self.audio_waveform_scene.width()
        new_center = current_center * (new_width / current_width)
        new_scroll = new_center - self.width() / 2
        self.horizontalScrollBar().setValue(new_scroll)

    def set_timestamp(self, timestamp):
        self.audio_waveform_scene.set_timestamp(timestamp)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier != Qt.KeyboardModifier.ShiftModifier:
            self.dragging = True
            self.dragging_initial_mouse_x = event.pos().x()
            self.dragging_initial_scroll_x = self.horizontalScrollBar().value()
        return super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if self.dragging:
            new_mouse_x = event.pos().x()
            new_scroll_x = self.dragging_initial_scroll_x - (new_mouse_x - self.dragging_initial_mouse_x)
            self.horizontalScrollBar().setValue(new_scroll_x)
        return super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        self.dragging = False
        return super().mouseReleaseEvent(event)

class AudioWaveformScene(QGraphicsScene):
    def __init__(self, audio_data, audio_player: audio.AudioPlayer, on_loop_change, *args, **kargs):
        super(AudioWaveformScene, self).__init__(*args, **kargs)
        self.setBackgroundBrush(Qt.GlobalColor.gray)
        self.audio_player = audio_player
        self.data = librosa.to_mono(audio_data)
        self.total_height = 180
        self.waveform_height = 150
        self.scale = 1.0
        self.duration = librosa.get_duration(self.data, sr=audio_player.audio_state.sampling_rate)
        self.timestamp = 0.0
        self.waveform = self.create_waveform(1200, self.waveform_height, self.data)
        self.waveform.setY(30)
        self.timeline = self.create_timeline(1200, 30, self.duration)
        self.add_cursor_to_scene()

        self.loop_start = 0.0
        self.loop_end = self.duration
        self.loop_rect = None
        self.add_loop_to_scene()

        self.setting_loop = False
        self.on_loop_change = on_loop_change

        self.placing_cursor = False
        self.placing_cursor_initial_x = 0.0

        self.timer = QTimer()
        self.timer.timeout.connect(self.on_timeout)
        self.timer.start(15)


    def on_timeout(self):
        self.set_timestamp(self.audio_player.current_timestamp)

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
        if self.on_loop_change is not None:
            self.on_loop_change(self.loop_start, self.loop_end)
        self.update_loop()

    def set_loop(self, start, end):
        self.loop_start = start
        self.loop_end = end
        if self.on_loop_change is not None:
            self.on_loop_change(self.loop_start, self.loop_end)
        self.update_loop()

    def set_timestamp(self, timestamp):
        self.timestamp = timestamp
        self.update_timestamp()

    def update_timestamp(self):
        new_pos = self.width() * self.timestamp / self.duration
        self.timestamp_cursor.setPos(new_pos, 0.0)
        # a bit dirty...while audio is playing, the current timestamp is controlled
        # by the audio player, and read by the GUI. When audio is not playing, the current
        # timestamp is controlled by the GUI and read by the audio player.
        if not self.audio_player.playing:
            self.audio_player.set_current_timestamp(self.timestamp)

    def zoom(self, factor):
        self.scale_waveform(self.scale * factor) 

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

    # should add at x = 0
    def add_cursor_to_scene(self):
        cursor_x = self.width() * self.timestamp / self.duration + 1
        cursor_height = self.total_height
        self.timestamp_cursor = self.addLine(cursor_x, 0, cursor_x, cursor_height, Qt.GlobalColor.red)

    def add_loop_to_scene(self):
        brush = QtGui.QBrush(QtGui.QColor(0, 0, 0, 100))
        pen = QtGui.QPen(QtGui.QColor(0, 0, 0, 100))
        pen.setStyle(Qt.PenStyle.NoPen)
        self.loop_rect = self.addRect(0, 0, self.width(), self.height(), pen, brush)
        self.update_loop()

    def update_loop(self):
        loop_start_in_px = self.width() * self.loop_start / self.duration
        loop_end_in_px = self.width() * self.loop_end / self.duration
        self.loop_rect.setRect(loop_start_in_px, 30, loop_end_in_px - loop_start_in_px, self.total_height - 30)
        self.update_rect()

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if event.modifiers() == Qt.KeyboardModifier.ShiftModifier and not self.audio_player.playing:
            timestamp = self.duration * event.scenePos().x() / self.width()
            self.setting_loop = True
            self.loop_start = timestamp
            self.loop_end = timestamp
            self.update_loop()
        else:
            self.placing_cursor = True
            self.placing_cursor_initial_x = event.screenPos().x()
        return super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        self.setting_loop = False
        if self.timestamp < self.loop_start or self.timestamp > self.loop_end:
            self.audio_player.set_current_timestamp(self.loop_start)
        if self.on_loop_change is not None:
            self.on_loop_change(self.loop_start, self.loop_end)

        if self.placing_cursor:
            new_x = event.screenPos().x()
            if abs(new_x - self.placing_cursor_initial_x) < 5:
                self.timestamp = self.duration * (event.scenePos().x() / self.width())
                self.update_timestamp()
            self.placing_cursor = False
        return super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        if self.setting_loop:
            timestamp = self.duration * event.scenePos().x() / self.width()
            if timestamp < self.loop_start:
                timestamp = self.loop_start
            self.loop_end = timestamp
            self.update_loop()
        # capture the move event for efficiency
        return None

    def create_waveform(self, width, height, audio_data):
        vertical_margin = 0
        effective_height = height - vertical_margin * 2
        chunks = int(len(audio_data) / 2000)
        chunk_pixel_width = float(width) / chunks
        chunk_sample_width = int(len(audio_data) / chunks)
        items = []
        pen = QtGui.QPen(Qt.PenStyle.NoPen)
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
            items.append(self.addRect(chunk_pixel_start, max_line_start, chunk_pixel_width, max_line_height, pen, Qt.GlobalColor.blue))
            items.append(self.addRect(chunk_pixel_start, rms_line_start, chunk_pixel_width, rms_line_height, pen, Qt.GlobalColor.darkBlue))
        waveform = self.createItemGroup(items)
        return waveform

    def create_timeline(self, width, height, duration):
        line = self.addLine(0.0, height, width, height, Qt.GlobalColor.black)
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
                tick = self.addLine(x, 0, x, height, Qt.GlobalColor.black)
                time_str = utils.seconds_to_time_str(second)
                font = QtGui.QFont("Courier New", 9)
                text = self.addText(time_str, font)
                text.setDefaultTextColor(Qt.GlobalColor.black)
                text.setPos(x, height - 28)
                text.setParentItem(line)
            else:
                tick = self.addLine(x, height - 6, x, height, Qt.GlobalColor.black)
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