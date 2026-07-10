# Sparky's sound engine. Every sound is SYNTHESIZED — little sine waves,
# sweeps, and noise cooked up with the standard-library wave module,
# cached as tiny .wav files in ~/.sparky/sounds, and played natively
# with QtMultimedia. No sound files shipped, no downloads.

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
        name = f"note_{key[1]}_{int(key[2] * 1000)}.wav"
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
        self.effects = {}  # key -> QSoundEffect (kept alive)

    def play(self, name, note, duration):
        if not (self.enabled and HAVE_AUDIO):
            return
        key = ("note", int(note), round(duration, 2)) if not name else name
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
