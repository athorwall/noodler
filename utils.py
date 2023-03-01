import librosa
import numpy

# Parses a string of the form XX or XX:XX into seconds. Throws ValueError if string cannot be parsed.
def get_duration_in_seconds(duration_str):
    parts = duration_str.split(":")
    if len(parts) > 2:
        parts = parts[0:2]
    seconds = float(parts[-1])
    if len(parts) > 1:
        seconds += 60 * float(parts[0])
    return seconds

# Converts a number of seconds into a time string of the form XX or XX:XX.
def seconds_to_time_str(seconds):
    minutes = seconds // 60
    remaining_seconds = seconds % 60
    if minutes > 0:
        return "{:.0f}:{:05,.2f}".format(minutes, remaining_seconds)
    else:
        return "{:05,.2f}".format(remaining_seconds)

def midi_to_piano_key(midi_note):
    # 21, not 20, so that piano keys are zero-indexed
    return midi_note - 21

def piano_key_to_midi(piano_key):
    return piano_key + 21

def note_to_piano_key(note):
    return midi_to_piano_key(librosa.note_to_midi(note, round_midi=True))

def piano_key_to_note(piano_key):
    return librosa.midi_to_note(piano_key_to_midi(piano_key))

# Performs librosa pitch-tracking and then groups the results by note.
# The result is an array for which arr[k, t] is the magnitude of note k (0 - 87)
# at time t.
def piptrack_by_note(y, sr, **kargs):
    pitches, magnitudes = librosa.piptrack(y=y, sr=sr, threshold=0.00, **kargs)
    cols = magnitudes.shape[1]
    result = numpy.zeros(88, cols)
    for t in range(0, cols):
        magnitudes_at_t = magnitudes[:,t]
        pitches_at_t = pitches[:,t]
        for (b, magnitude) in enumerate(magnitudes_at_t):
            pitch = pitches_at_t[b]
            note = librosa.hz_to_note(pitch)
            piano_key = note_to_piano_key(note)
            result[piano_key, t] += magnitude
    return result