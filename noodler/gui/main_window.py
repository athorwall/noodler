from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QInputDialog,
    QMainWindow,
    QWidget,
    QBoxLayout,
    QDockWidget,
    QLineEdit,
    QLabel,
    QCheckBox,
    QPushButton,
    QGridLayout,
    QFrame,
    QDoubleSpinBox,
    QSpinBox,
    QDialog,
    QGraphicsView,
    QGraphicsScene,
    QToolBar,
    QSizePolicy,
)
from PyQt6.QtCore import (
    Qt, 
    QTimer,
    QEvent,
)
from PyQt6 import QtGui
from pytube import YouTube
import librosa
import os
import audio_view
import events
import audio
import utils

MUSIC_PATH = "music"
ICONS_PATH = "icons"

def icon(path):
    return QtGui.QIcon("icons/{}".format(path))

class VerticalPitchTrackingWidget(QWidget):
    def __init__(self, audio_player, *args, **kargs):
        super(VerticalPitchTrackingWidget, self).__init__(*args, **kargs)

        self.audio_player = audio_player 

        main_layout = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        controls_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        
        self.timestamp_input = QLineEdit("00.00")
        self.timestamp_input.returnPressed.connect(self.on_set_timestamp)
        controls_layout.addWidget(self.timestamp_input)

        self.lock_to_timestamp_checkbox = QCheckBox("Lock to playback timestamp")
        self.lock_to_timestamp_checkbox.setChecked(True)
        controls_layout.addWidget(self.lock_to_timestamp_checkbox)

        self.threshold_input_label = QLabel("Threshold:")
        controls_layout.addWidget(self.threshold_input_label)
        self.threshold_input = QDoubleSpinBox()
        self.threshold_input.setValue(0.1)
        self.threshold_input.setMaximum(1.0)
        self.threshold_input.setMinimum(0.0)
        self.threshold_input.setSingleStep(0.1)
        controls_layout.addWidget(self.threshold_input)

        self.window_width_label = QLabel("Window size:")
        controls_layout.addWidget(self.window_width_label)
        self.window_width_input = QSpinBox()
        self.window_width_input.setValue(2048)
        self.window_width_input.setMinimum(1024)
        self.window_width_input.setMaximum(10000)
        controls_layout.addWidget(self.window_width_input)

        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.on_refresh)
        controls_layout.addWidget(refresh_button)
        
        main_layout.addLayout(controls_layout)
        self.view = VerticalPitchTrackingView()
        main_layout.addWidget(self.view)

        self.setLayout(main_layout)

        self.audio_data = None
        self.sr = None
        self.timestamp = 0.0

        self.timer = QTimer()
        self.timer.start(30)
        self.timer.timeout.connect(self.on_timeout)

    def on_set_timestamp(self):
        self.timestamp = utils.get_duration_in_seconds(self.timestamp_input.text())
        self.update_scene()
    
    def on_refresh(self):
        threshold = self.threshold_input.value()
        window_width = self.window_width_input.value()
        self.view.vertical_pitch_tracking_scene.update_params(threshold, window_width)

    def on_timeout(self):
        if self.lock_to_timestamp_checkbox.isChecked():
            if self.audio_player.audio_state is not None and self.audio_player.current_timestamp != self.timestamp:
                self.timestamp = self.audio_player.current_timestamp
                self.timestamp_input.setText(utils.seconds_to_time_str(self.timestamp))
                self.update_scene()

    def update_scene(self):
        self.view.vertical_pitch_tracking_scene.set_timestamp(self.timestamp)
        self.view.vertical_pitch_tracking_scene.update()

    def set_audio_data(self, audio_data, sr):
        self.audio_data = audio_data
        self.sr = sr
        threshold = self.threshold_input.value()
        window_width = self.window_width_input.value()
        self.view.vertical_pitch_tracking_scene.set_data(self.audio_data, self.sr, threshold, window_width)

class VerticalPitchTrackingView(QGraphicsView):
    def __init__(self, *args, **kargs):
        super(VerticalPitchTrackingView, self).__init__(*args, **kargs)

        self.vertical_pitch_tracking_scene = VerticalPitchTrackingScene()
        self.setScene(self.vertical_pitch_tracking_scene)

        self.setMinimumHeight(150)

        self.setFrameShape(QFrame.Shape.NoFrame)

        self.horizontalScrollBar().setValue(1)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.show()



class VerticalPitchTrackingScene(QGraphicsScene):
    def __init__(self, *args, **kargs):
        super(VerticalPitchTrackingScene, self).__init__(*args, **kargs)

        self.audio_data = None
        self.sr = None
        self.piptrack = None
        self.timestamp = 0.0

        self.setBackgroundBrush(Qt.GlobalColor.lightGray)

        self.rects = [None] * 88

    def set_data(self, audio_data, sr, threshold, window_width):
        self.pitches, self.magnitudes = librosa.piptrack(
            y=librosa.to_mono(y=audio_data), 
            sr=sr,
            threshold=threshold, 
            n_fft=window_width, 
            win_length=window_width,
        )
        self.audio_data = audio_data
        self.sr = sr
        self.create_chart()

    def update_params(self, threshold, window_width):
        self.pitches, self.magnitudes = librosa.piptrack(
            y=librosa.to_mono(y=self.audio_data), 
            sr=self.sr,
            threshold=threshold, 
            n_fft=window_width, 
            win_length=window_width,
        )
        self.update()

    def create_chart(self):
        self.clear()
        key_width = 20
        key_height = 100
        pen = QtGui.QPen(Qt.GlobalColor.black)
        brush = QtGui.QBrush(Qt.GlobalColor.white)
        for key in range(0, 88):
            self.rects[key] = self.addRect(key * key_width, 0, key_width, key_height, pen, brush)
            text = self.addText(utils.piano_key_to_note(key), QtGui.QFont("Courier New"))
            text.setDefaultTextColor(Qt.GlobalColor.black)
            text.setPos(key * key_width, key_height + 5)
        self.update()

    def set_timestamp(self, timestamp):
        self.timestamp = timestamp

    def update(self):
        duration = librosa.get_duration(y=self.audio_data, sr=self.sr)
        t = int(self.pitches.shape[1] * self.timestamp / duration)
        pitches = self.pitches[:,t]
        magnitudes = self.magnitudes[:,t]
        magnitudes_by_note = utils.group_by_note(pitches, magnitudes)
        max_magnitude = max(max(magnitudes), 50)
        #redunant, fix
        key_width = 20
        key_height = 100
        for key in range(0, 88):
            ms = magnitudes_by_note[key]
            h = key_height * (ms / max_magnitude)
            self.rects[key].setRect(key * key_width, key_height - h, key_width, h)

class MainView(QWidget):
    def __init__(self, audio_player, open_action, import_action, *args, **kargs):
        super(MainView, self).__init__(*args, **kargs)

        self.audio_view = None
        self.audio_player = audio_player
        layout = QBoxLayout(QBoxLayout.Direction.Down)

        self.open_button = QPushButton("Open...")
        self.open_button.clicked.connect(open_action.trigger)

        self.import_button = QPushButton("Import from YouTube...")
        self.import_button.clicked.connect(import_action.trigger)

        layout.addWidget(self.open_button)
        layout.addWidget(self.import_button)
        layout.addStretch(1)

        self.setLayout(layout)

    def show_audio(self, audio_data, on_loop_change):
        while self.layout().count() > 0:
            self.layout().takeAt(0)
        self.audio_view = audio_view.AudioWaveformView(audio_data, self.audio_player, on_loop_change, self)
        self.layout().addWidget(self.audio_view)

    def zoom_in(self):
        if self.audio_view != None:
            self.audio_view.zoom_in()

    def zoom_out(self):
        if self.audio_view != None:
            self.audio_view.zoom_out()

class EffectsDialog(QDialog):

    def __init__(self, play_rate, harmonic_only):
        super(EffectsDialog, self).__init__()

        layout = QGridLayout()

        self.rate_label = QLabel("Playback rate: ")
        self.rate_input = QDoubleSpinBox()
        self.rate_input.setValue(play_rate)
        self.rate_input.setMaximum(2.0)
        self.rate_input.setMinimum(0.1)

        layout.addWidget(self.rate_label, 0, 0)
        layout.addWidget(self.rate_input, 0, 1)

        self.harmonic_checkbox = QCheckBox("Enable HPSS")
        self.harmonic_checkbox.setChecked(harmonic_only)

        layout.addWidget(self.harmonic_checkbox, 1, 0, 1, 2)

        self.accept_button = QPushButton("OK")
        self.accept_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)

        layout.addWidget(self.accept_button, 2, 0)
        layout.addWidget(self.cancel_button, 2, 1)

        self.setLayout(layout)

class MainWindow(QMainWindow):

    def __init__(self, audio_player: audio.AudioPlayer):
        super().__init__()

        self.audio_player = audio_player
        self.audio_data = None

        self.main_view = None
        self.key_pressed = dict()

        self.harmonic_only = False
        self.play_rate = 1.0

        self.resize(1024, 768)
        self.setWindowTitle("Noodler")

        self.playback_toolbar = QToolBar("Playback")
        self.back_action = self.playback_toolbar.addAction(icon("back.png"), "Back")
        self.back_action.triggered.connect(lambda: QApplication.postEvent(self, events.BackEvent()))
        self.play_action = self.playback_toolbar.addAction(icon("play.png"), "Play")
        self.play_action.triggered.connect(lambda: QApplication.postEvent(self, events.PlayEvent()))
        self.pause_action = self.playback_toolbar.addAction(icon("pause.png"), "Pause")
        self.pause_action.triggered.connect(lambda: QApplication.postEvent(self, events.PauseEvent()))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.playback_toolbar)

        self.loop_toolbar = QToolBar("Selection")
        loop_layout = QGridLayout()
        self.range_start_widget = QLineEdit()
        self.range_start_widget.setMaximumWidth(50)
        loop_layout.addWidget(QLabel("Start:"), 0, 0)
        loop_layout.addWidget(self.range_start_widget, 0, 1)
        self.current_timestamp_widget = QLineEdit()
        self.current_timestamp_widget.setMaximumWidth(50)
        loop_layout.addWidget(QLabel("Current:"), 0, 2)
        loop_layout.addWidget(self.current_timestamp_widget, 0, 3)
        self.range_end_widget = QLineEdit()
        self.range_end_widget.setMaximumWidth(50)
        loop_layout.addWidget(QLabel("End:"), 1, 0)
        loop_layout.addWidget(self.range_end_widget, 1, 1)

        self.range_start_widget.returnPressed.connect(lambda: self.range_end_widget.setFocus())
        self.range_end_widget.returnPressed.connect(self.on_submit_range_selection)

        self.loop_checkbox = QCheckBox("Loop")
        self.loop_checkbox.setChecked(True)
        self.loop_checkbox.stateChanged.connect(self.on_set_loop_changed)
        loop_layout.addWidget(self.loop_checkbox, 0, 4)
        self.start_from_beginning_checkbox = QCheckBox("Start from Beginning")
        loop_layout.addWidget(self.start_from_beginning_checkbox, 1, 4)
        loop_layout.setColumnStretch(0, 0)
        loop_layout.setColumnStretch(1, 0)
        loop_layout.setColumnStretch(2, 0)
        loop_layout.setColumnStretch(3, 0)
        loop_layout.setColumnStretch(4, 1)
        loop_layout_widget = QWidget()
        loop_layout_widget.setLayout(loop_layout)
        loop_layout_widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        self.loop_toolbar.addWidget(loop_layout_widget)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.loop_toolbar)

        self.move_toolbar = QToolBar("Move Selection")
        self.move_backward_by_duration_action = self.move_toolbar.addAction(icon("left_arrow.png"), "Move Selection Backward by Duration")
        self.move_backward_by_duration_action.triggered.connect(lambda: QApplication.postEvent(self, events.PauseEvent()))
        self.move_by_duration_amount = QDoubleSpinBox()
        self.move_by_duration_amount.setSuffix("s")
        self.move_toolbar.addWidget(self.move_by_duration_amount)
        self.move_forward_by_duration_action = self.move_toolbar.addAction(icon("right_arrow.png"), "Move Selection Forward by Duration")
        self.move_forward_by_duration_action.triggered.connect(lambda: QApplication.postEvent(self, events.PauseEvent()))

        self.move_backward_by_duration_action.triggered.connect(
            lambda: QApplication.postEvent(self, events.ShiftLoopEvent(-self.move_by_duration_amount.value())))
        self.move_forward_by_duration_action.triggered.connect(
            lambda: QApplication.postEvent(self, events.ShiftLoopEvent(self.move_by_duration_amount.value())))

        self.move_backward_by_percentage_action = self.move_toolbar.addAction(icon("left_arrow.png"), "Move Selection Backward by Percentage")
        self.move_backward_by_percentage_action.triggered.connect(lambda: QApplication.postEvent(self, events.PauseEvent()))
        self.move_by_percentage_amount = QDoubleSpinBox()
        self.move_by_percentage_amount.setSuffix("%")
        self.move_by_percentage_amount.setMinimum(0.0)
        self.move_by_percentage_amount.setMaximum(100.0)
        self.move_toolbar.addWidget(self.move_by_percentage_amount)
        self.move_forward_by_percentage_action = self.move_toolbar.addAction(icon("right_arrow.png"), "Move Selection Forward by Percentage")
        self.move_forward_by_percentage_action.triggered.connect(lambda: QApplication.postEvent(self, events.PauseEvent()))

        self.move_backward_by_percentage_action.triggered.connect(
            lambda: self.on_shift_by_percent(-self.move_by_percentage_amount.value()))
        self.move_forward_by_percentage_action.triggered.connect(
            lambda: self.on_shift_by_percent(self.move_by_percentage_amount.value()))

        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.move_toolbar)

        self.vertical_pitch_tracking_dock_widget = QDockWidget("Vertical Pitch Tracking")
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.vertical_pitch_tracking_dock_widget)
        self.vertical_pitch_tracking_widget = VerticalPitchTrackingWidget(self.audio_player)
        self.vertical_pitch_tracking_dock_widget.setWidget(self.vertical_pitch_tracking_widget)

        fileMenu = self.menuBar().addMenu("File")
        self.openAction = fileMenu.addAction("Open...", QtGui.QKeySequence.StandardKey.Open)
        self.openAction.triggered.connect(self.open)
        self.importAction = fileMenu.addAction("Import From YouTube...", QtGui.QKeySequence("Ctrl+Y"))

        self.importAction.triggered.connect(self.import_from_youtube)

        viewMenu = self.menuBar().addMenu("View")
        self.zoomInAction = viewMenu.addAction("Zoom In", QtGui.QKeySequence.StandardKey.ZoomIn)
        self.zoomOutAction = viewMenu.addAction("Zoom Out", QtGui.QKeySequence.StandardKey.ZoomOut)

        toolsMenu = self.menuBar().addMenu("Tools")
        setPlaybackRateAction = toolsMenu.addAction("Set Playback Rate", QtGui.QKeySequence("Ctrl+R"))
        setPlaybackRateAction.triggered.connect(self.set_playback_rate)
        effectsAction = toolsMenu.addAction("Effects...", QtGui.QKeySequence("Ctrl+E"))
        effectsAction.triggered.connect(self.set_effects)

        self.timer = QTimer()
        self.timer.start(15)
        self.timer.timeout.connect(self.handle_key_presses)

        self.main_view = MainView(self.audio_player, self.openAction, self.importAction, self)
        self.zoomInAction.triggered.connect(self.main_view.zoom_in)
        self.zoomOutAction.triggered.connect(self.main_view.zoom_out)
        self.setCentralWidget(self.main_view)

        self.setFocus()

    def is_key_pressed(self, key):
        return key in self.key_pressed and self.key_pressed[key]

    def handle_key_presses(self):
        if self.audio_player.ready and not self.audio_player.playing:

            if self.is_key_pressed(Qt.Key.Key_D):
                if self.is_key_pressed(Qt.Key.Key_Shift):
                    self.audio_player.set_current_timestamp(self.audio_player.current_timestamp + 0.1)
                else:
                    self.audio_player.set_current_timestamp(self.audio_player.current_timestamp + 0.01)

            if self.is_key_pressed(Qt.Key.Key_A):
                if self.is_key_pressed(Qt.Key.Key_Shift):
                    self.audio_player.set_current_timestamp(self.audio_player.current_timestamp - 0.1)
                else:
                    self.audio_player.set_current_timestamp(self.audio_player.current_timestamp - 0.01)

            if self.main_view != None:
                if self.is_key_pressed(Qt.Key.Key_E):
                    if self.is_key_pressed(Qt.Key.Key_Shift):
                        self.main_view.audio_view.audio_waveform_scene.shift_loop(0.1)
                    else:
                        self.main_view.audio_view.audio_waveform_scene.shift_loop(0.01)
                if self.is_key_pressed(Qt.Key.Key_Q):
                    if self.is_key_pressed(Qt.Key.Key_Shift):
                        self.main_view.audio_view.audio_waveform_scene.shift_loop(-0.1)
                    else:
                        self.main_view.audio_view.audio_waveform_scene.shift_loop(-0.01)

    def on_shift_by_percent(self, percent):
        if self.main_view.audio_view is not None:
            width = self.main_view.audio_view.audio_waveform_scene.loop_end - self.main_view.audio_view.audio_waveform_scene.loop_start
            amount = width * percent / 100.0
            QApplication.postEvent(self, events.ShiftLoopEvent(amount))

    def on_submit_range_selection(self):
        try:
            start_second = utils.get_duration_in_seconds(self.range_start_widget.text())
            end_second = utils.get_duration_in_seconds(self.range_end_widget.text())
            if end_second < start_second:
                end_second = start_second
            event = events.SetLoopEvent(start_second, end_second)
            QApplication.postEvent(self, event)
            self.setFocus()
        except ValueError:
            return

    def on_set_loop_changed(self, state):
        enabled = False
        if state == Qt.CheckState.Checked.value:
            enabled = True
        event = events.SetLoopConfiguration(enabled)
        QApplication.postEvent(self, event)

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
        path = YouTube(url).streams.filter(file_extension='mp4').get_highest_resolution().download(output_path="music")
        self.load(path)

    def load(self, path):
        self.audio_data, sampling_rate = librosa.load(path, sr=None, mono=False)
        self.audio_player.set_audio_state(self.audio_data, sampling_rate, 1.0)
        self.main_view.show_audio(self.audio_data, self.on_loop_change)
        self.vertical_pitch_tracking_widget.set_audio_data(self.audio_data, sampling_rate)

    def on_loop_change(self, loop_start, loop_end):
        self.audio_player.set_start_timestamp(loop_start)
        self.audio_player.set_end_timestamp(loop_end)
        self.range_start_widget.setText(utils.seconds_to_time_str(loop_start))
        self.range_end_widget.setText(utils.seconds_to_time_str(loop_end))

    def set_playback_rate(self):
        (rate, _) = QInputDialog.getDouble(None, "Set Playback Rate", "Rate", value=1.0)
        # todo: handle the waiting period gracefully
        new_data = librosa.effects.time_stretch(y=self.audio_data, rate=rate)
        self.audio_player.set_audio_state(new_data, self.audio_player.audio_state.sampling_rate, rate)

    def set_effects(self):
        effects_dialog = EffectsDialog(self.play_rate, self.harmonic_only)
        result = effects_dialog.exec()
        if result == 1:
            self.play_rate = effects_dialog.rate_input.value()
            self.harmonic_only = effects_dialog.harmonic_checkbox.isChecked()
            new_data = self.audio_data
            if abs(self.play_rate- 1) > 0.01:
                new_data = librosa.effects.time_stretch(y=self.audio_data, sr=self.play_rate)
            if self.harmonic_only:
                new_data = librosa.effects.harmonic(y=new_data)
            self.audio_player.set_audio_state(new_data, self.audio_player.audio_state.sampling_rate, self.play_rate)
            self.vertical_pitch_tracking_widget.set_audio_data(self.audio_data, self.audio_player.audio_state.sampling_rate)


    def keyReleaseEvent(self, a0: QtGui.QKeyEvent) -> None:
        self.key_pressed[a0.key()] = False 
        return super().keyReleaseEvent(a0)

    def keyPressEvent(self, a0: QtGui.QKeyEvent) -> None:
        self.key_pressed[a0.key()] = True
        if not self.audio_player.ready:
            return super().keyPressEvent(a0)
        if a0.key() == Qt.Key.Key_Space:
            if self.audio_player.playing:
                QApplication.postEvent(self, events.PauseEvent())
            else:
                QApplication.postEvent(self, events.PlayEvent())
        return None

    def customEvent(self, event: QEvent):
        if event.type() == events.SetLoopEvent.TYPE:
            if not self.audio_player.playing and self.main_view.audio_view is not None:
                self.main_view.audio_view.audio_waveform_scene.set_loop(event.get_start(), event.get_end())
            return

        elif event.type() == events.ShiftLoopEvent.TYPE:
            if not self.audio_player.playing and self.main_view.audio_view is not None:
                self.main_view.audio_view.audio_waveform_scene.shift_loop(event.get_amount())
            return
        elif event.type() == events.PlayEvent.TYPE:
            if self.audio_player.audio_state is not None and not self.audio_player.playing:
                if self.start_from_beginning_checkbox.isChecked():
                    self.audio_player.set_current_timestamp(self.audio_player.start_timestamp)
                self.audio_player.play()
            return
        elif event.type() == events.PauseEvent.TYPE:
            self.audio_player.stop()
            return
        elif event.type() == events.BackEvent.TYPE:
            if self.main_view.audio_view is not None:
                if self.audio_player.playing:
                    self.audio_player.stop()
                    self.audio_player.set_current_timestamp(self.audio_player.start_timestamp)
                    self.audio_player.play()
                else:
                    self.audio_player.set_current_timestamp(self.main_view.audio_view.audio_waveform_scene.loop_start)
        elif event.type() == events.SetLoopConfiguration.TYPE:
            self.audio_player.set_loop(event.get_loop_enabled())
        return super().customEvent(event)
 