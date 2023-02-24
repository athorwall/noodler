from pytube import YouTube
import json
import librosa
import numpy
import os
import pyaudio
import time
from threading import Thread

CHECKPOINT_DATA_FILE = "checkpoint_data"

class TranscribeContext:
    def __init__(self, name, data, sampling_rate, on_change):
        self.name = name
        self.unaltered_data = data
        self.data = data.copy()
        self.play_rate = 1.0
        self.sampling_rate = sampling_rate
        self.playing = False
        self.current_timestamp = 0
        self.start_timestamp = 0
        self.end_timestamp = librosa.get_duration(self.data, sr=self.sampling_rate)
        self.restart = False
        self.checkpoints = dict()
        self.tempo = None
        self.time = None
        self.on_change = on_change

    def set_on_change(self, on_change):
        self.on_change = on_change

    def run(self):
        print("Ready to play " + self.name)
        print_help()
        while True:
            s = input("Enter a command, or press 'help' to see possible commands: ")
            parts = s.split()
            if len(parts) == 0:
                command = ""
            else:
                command = s.split()[0]
            args = s.split()[1:]
            if command == "play" or command == "":
                self.play_default()
            elif command == "loop":
                self.play_loop(args[0], args[1])
            elif command == "tempo":
                if len(args) == 1:
                    if args[0] == "auto":
                        self.tempo, beat_frames = librosa.beat.beat_track(y=self.unaltered_data, sr=self.sampling_rate)
                        print("Inferred tempo of {} bpm.".format(self.tempo))
                    else:
                        self.tempo = int(args[0])
                        print("Set tempo {} bpm.".format(self.tempo))
                else:
                    self.tempo = self.play_for_tempo()
                    print("Computed tempo of {} bpm.".format(self.tempo))
            elif command == "time":
                self.time = int(args[0])
                print("Set time to {} beats per measure.".format(self.time))
            elif command == "set":
                checkpoint = args[0]
                self.checkpoints[checkpoint] = self.current_timestamp
                print("Set checkpoint {} = {}".format(checkpoint, seconds_to_time_str(self.current_timestamp)))
            elif command == "playbackmode":
                mode = args[0]
                if mode == "restart":
                    self.restart = True
                elif mode == "continue":
                    self.restart = False
                else:
                    print("Unrecognized playback mode")
            elif command == "rate":
                rate = float(args[0])
                self.set_rate(rate)
            elif command == "save":
                self.save()
            elif command == "load":
                checkpoint_data = self.load()
                if self.name in checkpoint_data:
                    self.checkpoints = checkpoint_data[self.name]
            elif command == "help":
                print_help()
            elif command == "exit":
                print("Bye")
                break
            else:
                print("Unrecognized command. See help below.")
                print_help()

    def play_default(self):
        if self.current_timestamp < self.start_timestamp:
            self.current_timestamp = self.start_timestamp
        if self.current_timestamp > self.end_timestamp:
            self.current_timestamp = self.end_timestamp
        if self.restart:
            self.current_timestamp = self.start_timestamp
        self.play()


    def play_loop(self, start, end):
        if start not in self.checkpoints:
            print("Checkpoint " + start + " does not exist")
            return 
        if end not in self.checkpoints:
            print("Checkpoint " + end + " does not exist")
            return 
        self.current_timestamp = self.checkpoints[start]
        self.start_timestamp = self.checkpoints[start]
        self.end_timestamp = self.checkpoints[end]
        self.play()

    def set_start(self, start):
        self.start_timestamp = start
        if self.end_timestamp < self.start_timestamp:
            self.end_timestamp = self.start_timestamp
        self.clamp_timestamp()

    def set_end(self, end):
        self.end_timestamp = end
        if self.end_timestamp < self.start_timestamp:
            self.end_timestamp = self.start_timestamp
        self.clamp_timestamp()

    def clamp_timestamp(self):
        if self.current_timestamp < self.start_timestamp:
            self.current_timestamp = self.start_timestamp
        if self.current_timestamp > self.end_timestamp:
            self.current_timestamp = self.end_timestamp

    def stop(self):
        self.playing = False

    def play(self):
        if self.playing:
            return
        #t = Thread(target=self.play_internal, args=[])
        #t.start()

    def play_internal(self):
        self.playing = True
        current_frame = librosa.time_to_samples(self.current_timestamp / self.play_rate, sr=self.sampling_rate)
        def pyaudio_callback(in_data, frame_count, time_info, status):
            nonlocal self, current_frame
            start_frame = librosa.time_to_samples(self.start_timestamp / self.play_rate, sr=self.sampling_rate)
            if current_frame < start_frame:
                # a bit hacky, we can't have other classes write to current_frame while music is playing
                # but we want to ensure that it's updated if e.g. the loop shifts
                current_frame = start_frame
            end_frame = librosa.time_to_samples(self.end_timestamp / self.play_rate, sr=self.sampling_rate)
            (data, current_frame) = self.extract_audio_data(self.data, start_frame, end_frame, current_frame, frame_count)
            self.current_timestamp = librosa.samples_to_time(current_frame, sr=self.sampling_rate) * self.play_rate
            if self.playing:
                status = pyaudio.paContinue
            else:
                status = pyaudio.paComplete
            return (data, status)
        p = pyaudio.PyAudio()
        stream = p.open(rate=self.sampling_rate, channels=len(self.data.shape), format=pyaudio.paFloat32, output=True, stream_callback=pyaudio_callback)
        while stream.is_active():
            time.sleep(0.05)
        stream.close()
        p.terminate()

    def extract_audio_data(self, data, start_frame, end_frame, current_frame, frame_count):
        if len(data.shape) == 1:
            return self.extract_audio_data_mono(data, start_frame, end_frame, current_frame, frame_count)
        else:
            (left, _) = self.extract_audio_data_mono(data[0], start_frame, end_frame, current_frame, frame_count)
            (right, current_frame) = self.extract_audio_data_mono(data[1], start_frame, end_frame, current_frame, frame_count)
            result = numpy.empty((left.size + right.size,), dtype=left.dtype)
            result[0::2] = left
            result[1::2] = right
            return (result, current_frame)

    def extract_audio_data_mono(self, data, start_frame, end_frame, current_frame, frame_count):
        new_start_frame = current_frame + frame_count
        extracted_data = []
        if end_frame != None and new_start_frame > end_frame:
            extracted_data = numpy.concatenate((data[current_frame:], data[start_frame:(start_frame + new_start_frame - end_frame)]))
            current_frame = start_frame + new_start_frame - end_frame
        else:
            extracted_data = data[current_frame:new_start_frame]
            current_frame += frame_count
        return (extracted_data, current_frame)

    def set_rate(self, rate):
        print("Setting playback rate; this may take a moment...")
        self.data = librosa.effects.time_stretch(self.unaltered_data, rate=rate)
        print("Playback rate successfully set to {:.2f}".format(rate))
        self.play_rate = rate

    def save(self):
        checkpoint_data = self.load()
        checkpoint_data[self.name] = self.checkpoints
        with open(CHECKPOINT_DATA_FILE, 'w') as f:
            f.write(json.dumps(checkpoint_data))

    def load(self):
        if os.path.isfile(CHECKPOINT_DATA_FILE):
            with open(CHECKPOINT_DATA_FILE, 'r') as f:
                return json.loads(f.read())
        return dict()

    # Returns the duration in seconds represented by the given string, which must be in one of the following forms:
    # - seconds, e.g. "5s, 10 seconds, 6sec, 8 s, 10"
    # - bars, e.g. "5 bars"
    # - beats, e.g. "10 beats"
    # A duration with no units is considered to be in seconds already.
    def get_duration_in_seconds(self, duration):
        numerical_prefix = ""
        i = 0
        while i < len(duration) and ((duration[i] >= '0' and duration[i] <= '9') or duration[i] == '.' or duration[i] == '-'):
            numerical_prefix += duration[i]
            i += 1
        qty = float(numerical_prefix)
        units = duration[i:].strip()
        if units == "" or units == "s" or units == "sec" or units == "seconds":
            return qty
        if units == "beats":
            if self.tempo == None:
                print("Can't specify duration in beats because tempo is not configured.")
            return 60 * qty / self.tempo
        if units == "bars":
            if self.tempo == None or self.time == None:
                print("Can't specify duration in bars unless tempo and time are both configured.")
            return 60 * self.time * qty / self.tempo

def seconds_to_time_str(seconds):
    minutes = seconds // 60
    remaining_seconds = seconds % 60
    if minutes > 0:
        return "{:.0f}:{:05,.2f}".format(minutes, remaining_seconds)
    else:
        return "{:05,.2f}".format(remaining_seconds)

def print_help():
    print("")
    print("Commands:\n")
    print("\t- 'play' or no command: continue playing from the current playback timestamp")
    print("\t- 'tempo [t]': if t is provided, the tempo for the current track is configured to be that")
    print("\t               value, to support navigating by beat instead of time. If 'auto' is specified, noodler")
    print("\t               will attempt to infer the tempo using librosa's beat-tracking featuire. Otherwise, the music will")
    print("\t               play, and you can configure the tempo by hitting ENTER on the beat until the tempo seems")
    print("\t               correct. Then, enter any non-empty string to finish configuring the tempo.")
    print("\t               Once the tempo is configured, you can reference beats instead of seconds in commands,")
    print("\t               e.g. 'move 5 beats'.")
    print("\t- 'time [t]', e.g. 'time 4': configures the number of beats per measure. If the time and tempo are both")
    print("\t              configured, you can navigate the track with bars, e.g. 'move 1 bar'.")
    print("\t- 'set [c]': set a checkpoint at the current playback timestamp to reference it later")
    print("\t- 'from [c]': begin playback from the specified checkpoint. This disables any active loop.")
    print("\t- 'loop [t]': with one argument, begin playback from the current playback timestamp for a duration of t")
    print("\t- 'loop [c1] [c2]': with two arguments, begin playback from checkpoint c1, but loop back to c1 when c2 is reached")
    print("\t- 'move': move the playback timestamp forward by the specified number of seconds.")
    print("\t          If the timestamp is moved outside the bounds of the current loop, the loop is disabled.")
    print("\t- 'shift': shift the current playback loop forward by the specified number of seconds.")
    print("\t           Sets the playback timestamp to the start of the playback loop.")
    print("\t           Has no effect if there is no playback loop enabled.")
    print("\t- 'shiftend': Shift the end of the current playback loop by the specified number of seconds.")
    print("\t- 'shiftstart': Shift the end of the current playback loop by the specified number of seconds.")
    print("\t  'playbackmode [restart,continue]': sets the playback mode. In 'restart' mode, playback ")
    print("\t           always starts from the start of the current loop, or the start of the track if")
    print("\t           there is no active loop. In 'continue' mode, playback always starts from where it")
    print("\t           last ended.")
    print("\t- 'rate [r]': set the playback rate (0.5 is half-speed, 2.0 is double-speed, etc.)")
    print("\t- 'status': show the status of the playback timestamp, loop, and all checkpoints")
    print("\t- 'save': save all configuration (checkpoints, tempo, etc.) to a file so that it can be used again later")
    print("\t- 'load': load the saved checkpoint configuration for this track")
    print("\t- 'exit': exit the program")
    print("\t- 'help': show help")
    print("")
