from multiprocessing import Process, Queue
import queue
import librosa
import pyaudio
import numpy
from threading import Thread
import time

# Audio is played in a separate process to ensure that playback is not impacted
# by the UI. If audio is played from the same process as the UI, certain expensive operations
# (like zooming in on the waveform) can cause the playback to stutter.

# AudioState is the state required by the audio system to play audio.
class AudioState:
    def __init__(self, data = None, sampling_rate = None, play_rate = None):
        # This object can get quite big. If that's a problem, we'll instead transmit the filename.
        # In that case, the audio process will need to be responsible for modifications, e.g. play rate.
        self.data = data 
        self.sampling_rate = sampling_rate
        self.play_rate = play_rate

class PlayAudioCommand:
    TYPE = "play"

    def __init__(self, start_timestamp, end_timestamp, current_timestamp):
        self.start_timestamp = start_timestamp
        self.end_timestamp = end_timestamp
        self.current_timestamp = current_timestamp

    def type(self):
        return PlayAudioCommand.TYPE

class StopAudioCommand:
    TYPE = "stop"

    def type(self):
        return StopAudioCommand.TYPE

class RestartAudioCommand:
    TYPE = "restart"

    def type(self):
        return RestartAudioCommand.TYPE

# PlaybackState is the state of active audio playback which can be sent from the audio process back to the GUI process
# for UI purposes.
class PlaybackState:
    def __init__(self, timestamp):
        self.timestamp = timestamp

class AudioPlayer:

    def __init__(self):
        # The audio state queue is only ever written to by the GUI process and only ever read from
        # by the audio process to determine the state necessary to play audio.
        self.audio_state_queue = Queue()

        # The audio command queue is used by the GUI process to tell the audio process to play, stop,
        # etc. the audio.
        self.audio_command_queue = Queue()

        # The playback state queue is only ever written to by the audio process and only ever read from
        # by the GUI process to update the UI based on audio playback, e.g. move the cursor based on the 
        # playback timestamp.
        self.playback_state_queue = Queue()

        # These values are set by the GUI process, and will eventually be propagated to the audio process.
        # There's no guarantee that these values are the same values currently being used by the audio
        # process. 
        self.audio_state = None
        self.start_timestamp = None
        self.end_timestamp = None

        # This value can be set by the GUI process. Its value will be propagated to the audio process when audio playback begins.
        # While audio playback is occurring, this value will be updated by the audio process.
        self.current_timestamp = None

        self.ready = False
        self.playing = False

    def start(self):
        p = Process(target=audio_process, args=(self.audio_state_queue, self.audio_command_queue, self.playback_state_queue))
        p.start()

        t = Thread(target=self._playback_state_worker, args=[])
        t.start()

    def _playback_state_worker(self):
        playback_state = get_if_present(self.playback_state_queue)
        if playback_state != None:
            self.current_timestamp = playback_state.timestamp
        time.sleep(0.02)

    def set_audio_state(self, data, sampling_rate, play_rate):
        self.audio_state = AudioState(data, sampling_rate, play_rate)
        self.start_timestamp = 0.0
        self.end_timestamp = librosa.get_duration(data, sampling_rate)
        self.current_timestamp = 0.0
        self.ready = True
        self.audio_state_queue.put(self.audio_state)

    def set_start_timestamp(self, start_timestamp):
        self.start_timestamp = start_timestamp
        self._clamp_current_timestamp()

    def set_end_timestamp(self, end_timestamp):
        self.end_timestamp = end_timestamp
        self._clamp_current_timestamp()

    def set_current_timestamp(self, current_timestamp):
        self.current_timestamp = current_timestamp
        self._clamp_current_timestamp()

    def _clamp_current_timestamp(self):
        if self.current_timestamp < self.start_timestamp:
            self.current_timestamp = self.end_timestamp
        if self.current_timestamp > self.end_timestamp:
            self.current_timestamp = self.end_timestamp

    def play(self):
        # These should probably be synchronized in some way, but it will be safe as long as 
        # AudioPlayer is only accessed from a single thread.
        self.playing = True
        self.audio_command_queue.put(PlayAudioCommand(self.start_timestamp, self.end_timestamp, self.current_timestamp))

    def stop(self):
        self.playing = False
        self.audio_command_queue.put(StopAudioCommand())

    def restart(self):
        self.audio_command_queue.put(RestartAudioCommand())

def audio_process(audio_state_queue: Queue, audio_command_queue: Queue, playback_state_queue: Queue):

    stream = None
    audio_state = None

    p = pyaudio.PyAudio()
    while True:
        if stream is not None and stream.is_active():
            command = audio_command_queue.get()
            if command.type() == StopAudioCommand.TYPE:
                stream.close()
        else:
            command = get_if_present(audio_command_queue)
            if command is not None:
                if command.type() == PlayAudioCommand.TYPE and audio_state is not None:
                    print("Received play command")
                    stream = play_internal(
                        p, 
                        playback_state_queue, 
                        command.start_timestamp, 
                        command.end_timestamp, 
                        command.current_timestamp, 
                        audio_state,
                    )
            update = get_if_present(audio_state_queue)
            if update is not None:
                print("Received updated audio state")
                audio_state = update
    p.terminate()

def get_if_present(q):
    try:
        return q.get_nowait()
    except queue.Empty:
        return None

def play_internal(p, playback_queue, start_timestamp, end_timestamp, current_timestamp, audio_state):
    current_frame = librosa.time_to_samples(current_timestamp / audio_state.play_rate, sr=audio_state.sampling_rate)
    def pyaudio_callback(in_data, frame_count, time_info, status):
        nonlocal audio_state, start_timestamp, end_timestamp, current_timestamp, current_frame
        start_frame = librosa.time_to_samples(start_timestamp / audio_state.play_rate, sr=audio_state.sampling_rate)
        if current_frame < start_frame:
            # a bit hacky, we can't have other classes write to current_frame while music is playing
            # but we want to ensure that it's updated if e.g. the loop shifts
            current_frame = start_frame
        end_frame = librosa.time_to_samples(end_timestamp / audio_state.play_rate, sr=audio_state.sampling_rate)
        (data, current_frame) = extract_audio_data(audio_state.data, start_frame, end_frame, current_frame, frame_count)
        current_timestamp = librosa.samples_to_time(current_frame, sr=audio_state.sampling_rate) * audio_state.play_rate
        if playback_queue.empty():
            playback_queue.put(PlaybackState(current_timestamp))
        status = pyaudio.paContinue
        return (data, status)
    stream = p.open(rate=audio_state.sampling_rate, channels=len(audio_state.data.shape), format=pyaudio.paFloat32, output=True, stream_callback=pyaudio_callback)
    return stream

def extract_audio_data(data, start_frame, end_frame, current_frame, frame_count):
    if len(data.shape) == 1:
        return extract_audio_data_mono(data, start_frame, end_frame, current_frame, frame_count)
    else:
        (left, _) = extract_audio_data_mono(data[0], start_frame, end_frame, current_frame, frame_count)
        (right, current_frame) = extract_audio_data_mono(data[1], start_frame, end_frame, current_frame, frame_count)
        result = numpy.empty((left.size + right.size,), dtype=left.dtype)
        result[0::2] = left
        result[1::2] = right
        return (result, current_frame)

def extract_audio_data_mono(data, start_frame, end_frame, current_frame, frame_count):
    new_start_frame = current_frame + frame_count
    extracted_data = []
    if end_frame != None and new_start_frame > end_frame:
        extracted_data = numpy.concatenate((data[current_frame:], data[start_frame:(start_frame + new_start_frame - end_frame)]))
        current_frame = start_frame + new_start_frame - end_frame
    else:
        extracted_data = data[current_frame:new_start_frame]
        current_frame += frame_count
    return (extracted_data, current_frame)