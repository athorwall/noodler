from PyQt6.QtCore import (
    QEvent,
)

class SetLoopEvent(QEvent):
    TYPE = QEvent.registerEventType()

    def __init__(self, start, end):
        super(SetLoopEvent, self).__init__(SetLoopEvent.TYPE)

        self.start = start
        self.end = end

    def get_start(self):
        return self.start

    def get_end(self):
        return self.end

class SetLoopConfiguration(QEvent):
    TYPE = QEvent.registerEventType()

    def __init__(self, enable_loop):
        super(SetLoopConfiguration, self).__init__(SetLoopConfiguration.TYPE)

        self.enable_loop = enable_loop

    def get_loop_enabled(self):
        return self.enable_loop

class PlayEvent(QEvent):
    TYPE = QEvent.registerEventType()

    def __init__(self):
        super(PlayEvent, self).__init__(PlayEvent.TYPE)

class PauseEvent(QEvent):
    TYPE = QEvent.registerEventType()

    def __init__(self):
        super(PauseEvent, self).__init__(PauseEvent.TYPE)

class BackEvent(QEvent):
    TYPE = QEvent.registerEventType()

    def __init__(self):
        super(BackEvent, self).__init__(BackEvent.TYPE)
