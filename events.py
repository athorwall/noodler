from PyQt6.QtCore import (
    QEvent,
)

class SetLoopEvent(QEvent):
    TYPE = QEvent.registerEventType()

    def __init__(self, start, end, *args, **kargs):
        super(SetLoopEvent, self).__init__(SetLoopEvent.TYPE, *args, **kargs)

        self.start = start
        self.end = end

    def get_start(self):
        return self.start

    def get_end(self):
        return self.end

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
