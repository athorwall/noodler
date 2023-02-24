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
)
from PyQt6.QtCore import (
    Qt, 
    QTimer,
    QEvent,
)
from PyQt6 import QtGui
import transcribe
from pytube import YouTube
import librosa
import os
import audio_view
import events
import audio

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
        
        self.move_by_time_widget = MoveSelectionWidget(1, 10, "s", lambda value: 0)
        layout.addWidget(self.move_by_time_widget)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setFrameShadow(QFrame.Shadow.Plain)
        layout.addWidget(sep2)

        self.move_by_proportion_widget = MoveSelectionWidget(50, 80, "%", lambda value: 0)
        layout.addWidget(self.move_by_proportion_widget)

        layout.addStretch(1)

        self.setLayout(layout)

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

        self.start_from_beginning_checkbox = QCheckBox("Start from beginning of loop")
        layout.addWidget(self.start_from_beginning_checkbox)

        self.setLayout(layout)

class MoveSelectionWidget(QWidget):
    def __init__(self, smaller_value, bigger_value, unit, on_change, *args, **kargs):
        super(MoveSelectionWidget, self).__init__(*args, **kargs)

        layout = QGridLayout()

        smaller_text = "{}{}".format(smaller_value, unit)
        bigger_text = "{}{}".format(bigger_value, unit)

        self.double_left_widget = MoveSelectionWidget.tool_button(bigger_text, icon(DOUBLE_LEFT_ARROW))
        layout.addWidget(self.double_left_widget, 0, 0)
        self.left_widget = MoveSelectionWidget.tool_button(smaller_text, icon(LEFT_ARROW))
        layout.addWidget(self.left_widget, 0, 1)

        self.right_widget = MoveSelectionWidget.tool_button(smaller_text, icon(RIGHT_ARROW))
        layout.addWidget(self.right_widget, 0, 2)
        self.double_right_widget = MoveSelectionWidget.tool_button(bigger_text, icon(DOUBLE_RIGHT_ARROW))
        layout.addWidget(self.double_right_widget, 0, 3)

        self.custom_left_widget = QToolButton()
        self.custom_left_widget.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.custom_left_widget.setIcon(icon(LEFT_ARROW))
        layout.addWidget(self.custom_left_widget, 1, 0)

        self.custom_shift_widget = QLineEdit("1.0")
        layout.addWidget(self.custom_shift_widget, 1, 1, 1, 2)

        self.custom_right_widget = QToolButton()
        self.custom_right_widget.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.custom_right_widget.setIcon(icon(RIGHT_ARROW))
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
        layout.addWidget(self.from_widget)
        layout.addWidget(self.to_label)
        layout.addWidget(self.to_widget)

        self.setLayout(layout)
        self.setMaximumWidth(250)

    def on_set_start(self, text):
        # for now only support seconds
        try:
            start_second = float(text)
            end_second = float(self.to_widget.text())
            event = events.SetLoopEvent(start_second, end_second)
            app.postEvent(window, event)
        except ValueError:
            return

    def on_set_end(self, text):
        try:
            start_second = float(self.from_widget.text())
            end_second = float(text)
            event = events.SetLoopEvent(start_second, end_second)
            app.postEvent(window, event)
        except ValueError:
            return


class MainView(QWidget):
    def __init__(self, audio_player, *args, **kargs):
        super(MainView, self).__init__(*args, **kargs)

        self.audio_view = audio_view.AudioWaveformView(audio_player, self)
        layout = QBoxLayout(QBoxLayout.Direction.Down)
        layout.addWidget(self.audio_view)

        self.setLayout(layout)

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
        self.dock_widget.setWidget(NavigationDock())

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
        data, sampling_rate = librosa.load(path, sr=None, mono=False)
        self.audio_player.set_audio_state(data, sampling_rate, 1.0)
        self.main_view = MainView(self.audio_player, self)
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
            if self.audio_player.playing:
                self.audio_player.stop()
            else:
                self.audio_player.play()
        return None

    def customEvent(self, event: QEvent):
        if event.type() == events.SetLoopEvent.TYPE:
            return
        elif event.type() == events.PlayEvent.TYPE:
            self.audio_player.play()
            return
        elif event.type() == events.PauseEvent.TYPE:
            self.audio_player.stop()
            return
        return super().customEvent(event)
 
if __name__ == '__main__':
    audio_player = audio.AudioPlayer()
    audio_player.start()

    app = QApplication([])
    app.setStyle('macos')
    window = MainWindow(audio_player)
    window.show()
    app.exec()