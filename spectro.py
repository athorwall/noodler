import librosa
import matplotlib.pyplot as plt
import numpy as np
import time

y, sr = librosa.load("music/Bill Evans Trio - Alice In Wonderland (Take 2).mp4", sr=None)
#y = librosa.effects.harmonic(y, margin = 8)
pitches, magnitudes = librosa.piptrack(y=y, sr=sr, threshold=0.00)
duration = librosa.get_duration(y=y)
num_times = len(pitches[0])
print("Ready!")

while True:
    timestamp = float(input("Timestamp: "))
    t = int(num_times * timestamp / duration)
    ms = magnitudes[:,t]
    ps = pitches[:,t]
    pitch_indices = []
    for b in enumerate(ms):
        if b[1] > 0.0:
            pitch_indices.append(b)
    magnitude_by_note = dict()
    for index in pitch_indices:
        i = index[0]
        p = ps[i]
        m = index[1]
        note = librosa.hz_to_note(p)
        if note not in magnitude_by_note:
            magnitude_by_note[note] = 0.0
        magnitude_by_note[note] += m
        
    for note in magnitude_by_note.keys():
        print("Note: {}, magnitude: {}".format(note, magnitude_by_note[note]))



#print("harmonic")
#y = np.minimum(y,
#                           librosa.decompose.nn_filter(y,
#                                                       aggregate=np.median,
#                                                       metric='cosine'))
#                                                    
#print("minimum")
#
#
## chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
## fig, ax = plt.subplots()
## img = librosa.display.specshow(chroma, y_axis='chroma', x_axis='time', ax=ax)
## ax.set(title='Chromagram demonstration')
## fig.colorbar(img, ax=ax)
#
#C = librosa.cqt(y=y, sr=sr)
#C_db = librosa.amplitude_to_db(np.abs(C), ref=np.max)
#
#fig, ax = plt.subplots()
#librosa.display.specshow(C_db, y_axis='cqt_hz', x_axis='time', ax=ax)
#ax.set(title='Frequency (Hz) axis decoration')
#
#fig, ax = plt.subplots()
#librosa.display.specshow(C_db, y_axis='cqt_note', x_axis='time', ax=ax)
#ax.set(title='Pitch axis decoration')
#
#fig.show()
#fig.savefig("test.png",)
#
#input()