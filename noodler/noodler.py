from PyQt6.QtWidgets import QApplication
import audio
import audio
import gui

if __name__ == '__main__':
    audio_player = audio.AudioPlayer()
    audio_player.start()

    app = QApplication([])
    app.setStyle('macos')
    window = gui.MainWindow(audio_player)
    window.show()
    app.exec()