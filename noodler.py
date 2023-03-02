from PyQt6.QtWidgets import QApplication
from noodler import audio
from noodler import gui

if __name__ == '__main__':
    audio_player = audio.AudioPlayer()
    audio_player.start()

    app = QApplication([])
    app.setStyle('macos')
    window = gui.MainWindow(audio_player)
    window.show()
    app.exec()