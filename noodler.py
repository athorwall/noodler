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
    QToolButton,
    QGridLayout,
    QFrame,
    QDoubleSpinBox,
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
LEFT_ARROW = "angle-left.png"
DOUBLE_LEFT_ARROW = "angle-double-left.png"
RIGHT_ARROW = "angle-right.png"
DOUBLE_RIGHT_ARROW = "angle-double-right.png"
PLAY = "play.png"
PAUSE = "pause.png"
BACK = "previous.png"

def icon(path):
    return QtGui.QIcon("icons/{}".format(path))

class NavigationDock(QWidget):
    def __init__(self, *args, **kargs):
        super(NavigationDock, self).__init__(*args, **kargs)

        layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)

        self.selection_widget = SelectionWidget()
        layout.addWidget(self.selection_widget)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.VLine)
        sep1.setFrameShadow(QFrame.Shadow.Plain)
        layout.addWidget(sep1)
        
        self.move_by_time_widget = MoveSelectionWidget(1, 10, "s", lambda amount: app.postEvent(window, events.ShiftLoopEvent(amount)))
        layout.addWidget(self.move_by_time_widget)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setFrameShadow(QFrame.Shadow.Plain)
        layout.addWidget(sep2)

        self.move_by_proportion_widget = MoveSelectionWidget(50, 80, "%", self.on_shift_by_percent)
        layout.addWidget(self.move_by_proportion_widget)

        layout.addStretch(1)

        self.setLayout(layout)

    def on_shift_by_percent(self, percent):
        if window.main_view.audio_view is not None:
            width = window.main_view.audio_view.audio_waveform_scene.loop_end - window.main_view.audio_view.audio_waveform_scene.loop_start
            amount = width * percent / 100.0
            app.postEvent(window, events.ShiftLoopEvent(amount))

class PlayControls(QWidget):
    def __init__(self, *args, **kargs):
        super(PlayControls, self).__init__(*args, **kargs)

        layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)

        self.back_button = QToolButton()
        self.back_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.back_button.setIcon(icon(BACK))
        self.back_button.clicked.connect(lambda: app.postEvent(window, events.BackEvent()))
        layout.addWidget(self.back_button)

        self.play_button = QToolButton()
        self.play_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.play_button.setIcon(icon(PLAY))
        self.play_button.clicked.connect(lambda: app.postEvent(window, events.PlayEvent()))
        layout.addWidget(self.play_button)

        self.pause_button = QToolButton()
        self.pause_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.pause_button.setIcon(icon(PAUSE))
        self.pause_button.clicked.connect(lambda: app.postEvent(window, events.PauseEvent()))
        layout.addWidget(self.pause_button)

        self.setLayout(layout)

class SelectionWidget(QWidget):
    def __init__(self, *args, **kargs):
        super(SelectionWidget, self).__init__(*args, **kargs)

        layout = QBoxLayout(QBoxLayout.Direction.TopToBottom)

        self.play_controls_widget = PlayControls()
        layout.addWidget(self.play_controls_widget)

        self.range_selection_widget = RangeSelectionWidget()
        layout.addWidget(self.range_selection_widget)

        self.loop_checkbox = QCheckBox("Loop")
        layout.addWidget(self.loop_checkbox)
        self.loop_checkbox.setChecked(True)
        self.loop_checkbox.stateChanged.connect(self.on_set_loop_changed)

        self.start_from_beginning_checkbox = QCheckBox("Start from beginning of loop")
        layout.addWidget(self.start_from_beginning_checkbox)

        self.setLayout(layout)

    def on_set_loop_changed(self, state):
        enabled = False
        if state == Qt.CheckState.Checked.value:
            enabled = True
        event = events.SetLoopConfiguration(enabled)
        app.postEvent(window, event)

class MoveSelectionWidget(QWidget):
    def __init__(self, smaller_value, bigger_value, unit, on_change, *args, **kargs):
        super(MoveSelectionWidget, self).__init__(*args, **kargs)

        self.on_change = on_change

        layout = QGridLayout()

        smaller_text = "{}{}".format(smaller_value, unit)
        bigger_text = "{}{}".format(bigger_value, unit)

        self.double_left_widget = MoveSelectionWidget.tool_button(bigger_text, icon(DOUBLE_LEFT_ARROW))
        self.double_left_widget.clicked.connect(lambda: on_change(-bigger_value))
        layout.addWidget(self.double_left_widget, 0, 0)
        self.left_widget = MoveSelectionWidget.tool_button(smaller_text, icon(LEFT_ARROW))
        self.left_widget.clicked.connect(lambda: on_change(-smaller_value))
        layout.addWidget(self.left_widget, 0, 1)

        self.right_widget = MoveSelectionWidget.tool_button(smaller_text, icon(RIGHT_ARROW))
        self.right_widget.clicked.connect(lambda: on_change(smaller_value))
        layout.addWidget(self.right_widget, 0, 2)
        self.double_right_widget = MoveSelectionWidget.tool_button(bigger_text, icon(DOUBLE_RIGHT_ARROW))
        self.double_right_widget.clicked.connect(lambda: on_change(bigger_value))
        layout.addWidget(self.double_right_widget, 0, 3)

        self.custom_shift_widget = QDoubleSpinBox()
        self.custom_shift_widget.setSuffix(unit)
        self.custom_shift_widget.setValue(smaller_value)
        self.custom_shift_widget.setMaximum(1000.0)
        layout.addWidget(self.custom_shift_widget, 1, 1, 1, 2)

        self.custom_left_widget = QToolButton()
        self.custom_left_widget.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.custom_left_widget.setIcon(icon(LEFT_ARROW))
        self.custom_left_widget.clicked.connect(lambda: on_change(-self.custom_shift_widget.value()))
        layout.addWidget(self.custom_left_widget, 1, 0)

        self.custom_right_widget = QToolButton()
        self.custom_right_widget.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.custom_right_widget.setIcon(icon(RIGHT_ARROW))
        self.custom_right_widget.clicked.connect(lambda: on_change(self.custom_shift_widget.value()))
        layout.addWidget(self.custom_right_widget, 1, 3)

        self.setLayout(layout)

    def tool_button(text, icon):
        widget = QToolButton()
        widget.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        widget.setIcon(icon)
        widget.setText(text)
        return widget

class RangeSelectionWidget(QWidget):
    def __init__(self, *args, **kargs):
        super(RangeSelectionWidget, self).__init__(*args, **kargs)

        layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)

        self.from_widget = QLineEdit()
        self.from_widget.textEdited.connect(self.on_set_start)

        self.to_label = QLabel("to")
        self.to_widget = QLineEdit()
        self.to_widget.textEdited.connect(self.on_set_end)

        self.from_widget.returnPressed.connect(lambda: self.to_widget.setFocus())
        self.to_widget.returnPressed.connect(lambda: window.setFocus())

        layout.addWidget(self.from_widget)
        layout.addWidget(self.to_label)
        layout.addWidget(self.to_widget)

        self.setLayout(layout)
        self.setMaximumWidth(250)

    def on_set_start(self, text):
        # for now only support seconds

        try:
            start_second = utils.get_duration_in_seconds(text)
            end_second = utils.get_duration_in_seconds(self.to_widget.text())
            if end_second < start_second:
                end_second = start_second
            event = events.SetLoopEvent(start_second, end_second)
            app.postEvent(window, event)
        except ValueError:
            return

    def on_set_end(self, text):
        try:
            start_second = utils.get_duration_in_seconds(self.from_widget.text())
            end_second = utils.get_duration_in_seconds(text)
            if end_second < start_second:
                end_second = start_second
            event = events.SetLoopEvent(start_second, end_second)
            app.postEvent(window, event)
        except ValueError:
            return


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
        self.audio_view = audio_view.AudioWaveformView(audio_data, audio_player, on_loop_change, self)
        self.layout().addWidget(self.audio_view)

    def zoom_in(self):
        if self.audio_view != None:
            self.audio_view.zoom_in()

    def zoom_out(self):
        if self.audio_view != None:
            self.audio_view.zoom_out()

class MainWindow(QMainWindow):

    def __init__(self, audio_player: audio.AudioPlayer):
        super().__init__()

        self.audio_player = audio_player
        self.audio_data = None

        self.main_view = None
        self.key_pressed = dict()

        self.resize(800, 600)
        self.setWindowTitle("Noodler")

        self.dock_widget = QDockWidget("Navigation")
        self.addDockWidget(Qt.DockWidgetArea.TopDockWidgetArea, self.dock_widget)
        self.navigation_widget = NavigationDock()
        self.dock_widget.setWidget(self.navigation_widget)

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
                    self.audio_player.set_current_timestamp(self.audio_player.current_timestamp + 0.5)
                else:
                    self.audio_player.set_current_timestamp(self.audio_player.current_timestamp + 0.05)

            if self.is_key_pressed(Qt.Key.Key_A):
                if self.is_key_pressed(Qt.Key.Key_Shift):
                    self.audio_player.set_current_timestamp(self.audio_player.current_timestamp - 0.5)
                else:
                    self.audio_player.set_current_timestamp(self.audio_player.current_timestamp - 0.05)

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
        self.audio_data, sampling_rate = librosa.load(path, sr=None, mono=False)
        self.audio_player.set_audio_state(self.audio_data, sampling_rate, 1.0)
        self.main_view.show_audio(self.audio_data, self.on_loop_change)

    def on_loop_change(self, loop_start, loop_end):
        self.audio_player.set_start_timestamp(loop_start)
        self.audio_player.set_end_timestamp(loop_end)

    # TODO: not working right now
    def set_playback_rate(self):
        (rate, _) = QInputDialog.getDouble(None, "Set Playback Rate", "Rate", value=1.0)
        # todo: handle the waiting period gracefully
        new_data = librosa.effects.time_stretch(self.audio_data, rate)
        self.audio_player.set_audio_state(new_data, self.audio_player.audio_state.sampling_rate, rate)

    def keyReleaseEvent(self, a0: QtGui.QKeyEvent) -> None:
        self.key_pressed[a0.key()] = False 
        return super().keyReleaseEvent(a0)

    def keyPressEvent(self, a0: QtGui.QKeyEvent) -> None:
        self.key_pressed[a0.key()] = True
        if not self.audio_player.ready:
            return super().keyPressEvent(a0)
        if a0.key() == Qt.Key.Key_Space:
            if self.audio_player.playing:
                app.postEvent(self, events.PauseEvent())
            else:
                app.postEvent(self, events.PlayEvent())
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
            if self.navigation_widget.selection_widget.start_from_beginning_checkbox.isChecked():
                self.audio_player.set_current_timestamp(self.audio_player.start_timestamp)
            self.audio_player.play()
            return
        elif event.type() == events.PauseEvent.TYPE:
            self.audio_player.stop()
            return
        elif event.type() == events.BackEvent.TYPE:
            if self.audio_player.playing:
                self.audio_player.stop()
                self.audio_player.set_current_timestamp(self.audio_player.start_timestamp)
                self.audio_player.play()
            else:
                self.audio_player.set_current_timestamp(self.main_view.audio_view.audio_waveform_scene.loop_start)
        elif event.type() == events.SetLoopConfiguration.TYPE:
            self.audio_player.set_loop(event.get_loop_enabled())
        return super().customEvent(event)
 
if __name__ == '__main__':
    audio_player = audio.AudioPlayer()
    audio_player.start()

    app = QApplication([])
    app.setStyle('macos')
    window = MainWindow(audio_player)
    window.show()
    app.exec()