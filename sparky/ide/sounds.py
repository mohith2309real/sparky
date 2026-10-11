# Sparky's sound engine. Every sound is SYNTHESIZED — little sine waves,
# sweeps, and noise cooked up with the standard-library wave module,
# cached as tiny .wav files in ~/.sparky/sounds, and played natively
# with QtMultimedia. No sound files shipped, no downloads.

import hashlib
import math
import random
import struct
import wave
from pathlib import Path

try:
    from PyQt6.QtCore import QUrl
    from PyQt6.QtMultimedia import QSoundEffect
    HAVE_AUDIO = True
except ImportError:  # pragma: no cover — sounds just go quiet
    HAVE_AUDIO = False

from ..lang.music import INSTRUMENTS, SOUND_NAMES, frequency

RATE = 22050
CACHE = Path.home() / ".sparky" / "sounds"

# note 1..14 = two do-re-mi octaves of C major starting at middle C
MAJOR_STEPS = (0, 2, 4, 5, 7, 9, 11)


def note_frequency(note):
    octave, degree = divmod(int(note) - 1, 7)
    semitones = octave * 12 + MAJOR_STEPS[degree]
    return 261.63 * (2 ** (semitones / 12))


# ---------- tiny synthesizer ----------

def envelope(i, total, attack=0.01, release=0.25):
    """Soft start, fading end — no clicks."""
    t = i / total
    a = min(1.0, (i / RATE) / attack) if attack else 1.0
    r = min(1.0, (1.0 - t) / release) if release else 1.0
    return a * min(1.0, r)


def render(duration, voice):
    total = max(1, int(RATE * duration))
    samples = []
    phase = 0.0
    for i in range(total):
        t = i / RATE
        freq, amp = voice(t, i / total)
        phase += 2 * math.pi * freq / RATE
        value = math.sin(phase) * amp * envelope(i, total)
        samples.append(int(max(-1.0, min(1.0, value)) * 32000))
    return samples


def render_noise(duration, level):
    total = max(1, int(RATE * duration))
    value = 0.0
    samples = []
    for i in range(total):
        # smoothed noise sounds drum-ish instead of harsh static
        value = value * 0.6 + random.uniform(-1, 1) * 0.4
        decay = (1.0 - i / total) ** 2
        samples.append(int(value * level * decay * 32000))
    return samples


def synthesize(key):
    """Return raw samples for a named sound or ('note', n, duration)."""
    if isinstance(key, tuple) and key[0] == 'music':
        _, instrument, notes, duration = key
        if instrument not in INSTRUMENTS or not notes:
            return []
        total = max(1, int(RATE * duration))
        samples=[]
        harmonics={'piano':(1,.35,.12), 'xylophone':(1,0,.4), 'guitar':(1,.55,.25),
                   'organ':(1,.45,.3,.15), 'flute':(1,.08,.03)}[instrument]
        for i in range(total):
            t=i/RATE
            fade=math.exp(-t*({'piano':3,'xylophone':7,'guitar':4,'organ':0,'flute':.5}[instrument]))
            tone=sum(sum(weight*math.sin(2*math.pi*frequency(note)*(h+1)*t)
                         for h,weight in enumerate(harmonics)) for note in notes)
            value=tone/max(1,len(notes))/sum(harmonics)*fade*envelope(i,total,attack=.015,release=.12)
            samples.append(int(max(-1,min(1,value)) * 30000))
        return samples
    recipes={'coin':(.18,900,1500), 'splash':(.45,180,70), 'whoosh':(.4,100,1200),
             'meow':(.5,600,300), 'woof':(.28,140,80), 'applause':(.7,800,400),
             'bell':(.8,1320,1320), 'click':(.04,1800,1800), 'crash':(.6,100,30),
             'chirp':(.18,1200,2400), 'bubble':(.2,300,900), 'swoosh':(.35,1200,100),
             'zap':(.15,2200,160), 'bounce':(.25,180,400), 'sparkle':(.6,1800,2600),
             'drip':(.12,700,250), 'knock':(.1,180,150), 'whistle':(.7,1100,1600),
             'success':(.5,523,1046), 'oops':(.4,440,180)}
    if key in recipes:
        duration,start,end=recipes[key]
        if key in ('splash','applause','crash','whoosh','swoosh'):
            return render_noise(duration,.8)
        return render(duration,lambda t,p:(start+(end-start)*p,.8*(1-p)**.5))
    if key == "pop":
        return render(0.12, lambda t, p: (420 * (1 - p * 0.8), 0.9))
    if key == "ding":
        return render(0.55, lambda t, p: (880, 0.8 * (1 - p) ** 1.5))
    if key == "boing":
        return render(0.45, lambda t, p:
                      (230 + 90 * math.sin(t * 42) * (1 - p), 0.85))
    if key == "laser":
        return render(0.22, lambda t, p: (1400 - 1250 * p, 0.8))
    if key == "jump":
        return render(0.2, lambda t, p: (160 + 480 * p, 0.85))
    if key == "drum":
        return render_noise(0.22, 0.9)
    if key == "tada":
        first = render(0.22, lambda t, p: (523.25, 0.85))
        second = render(0.5, lambda t, p: (784.0, 0.85 * (1 - p) ** 0.8))
        return first + second
    if isinstance(key, tuple) and key[0] == "note":
        _, note, duration = key
        freq = note_frequency(note)

        def voice(t, p):
            # a touch of second harmonic makes it warmer than a pure sine
            return (freq, 0.75 * (1 - p) ** 0.6)
        base = render(duration, voice)
        shimmer = render(duration, lambda t, p: (freq * 2, 0.12 * (1 - p)))
        return [a + b for a, b in zip(base, shimmer)]
    return []


def wav_path(key):
    """Synthesize once, then reuse the cached .wav forever."""
    CACHE.mkdir(parents=True, exist_ok=True)
    if isinstance(key, tuple):
        name = hashlib.sha256(repr(key).encode()).hexdigest()+".wav"
    else:
        name = f"{key}.wav"
    path = CACHE / name
    if not path.exists():
        samples = synthesize(key)
        with wave.open(str(path), "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(RATE)
            f.writeframes(struct.pack(f"<{len(samples)}h", *(
                max(-32768, min(32767, s)) for s in samples)))
    return path


# ---------- the bank the IDE talks to ----------

class SoundBank:
    def __init__(self):
        self.enabled = True
        self.volume = 0.8
        self.events = {'run': True, 'done': True, 'error': True}
        self.effects = {}  # key -> QSoundEffect (kept alive)

    def play(self, name, note, duration):
        if not (self.enabled and HAVE_AUDIO):
            return
        key = ("note", int(note), round(duration, 2)) if not name else name
        self.play_key(key)

    def play_music(self, instrument, notes, duration):
        if not (self.enabled and HAVE_AUDIO):
            return
        if instrument not in INSTRUMENTS or not notes or len(notes)>8:
            return
        self.play_key(('music', instrument, tuple(notes), round(max(.05,min(4,duration)),2)))

    def event(self, kind):
        if self.events.get(kind, False):
            self.play({'run':'pop', 'done':'success', 'error':'oops'}[kind],0,0)

    def stop(self):
        for effect in self.effects.values():
            effect.stop()

    def play_key(self, key):
        effect = self.effects.get(key)
        if effect is None:
            try:
                path = wav_path(key)
            except OSError:
                return
            effect = QSoundEffect()
            effect.setSource(QUrl.fromLocalFile(str(path)))
            self.effects[key] = effect
        effect.setVolume(self.volume)
        effect.play()
