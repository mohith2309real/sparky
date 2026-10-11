"""Offline music vocabulary shared by the language, piano and sound engine."""
import re
INSTRUMENTS = ('piano', 'xylophone', 'guitar', 'organ', 'flute')
SOUND_NAMES = ('pop', 'ding', 'boing', 'laser', 'drum', 'tada', 'jump',
               'coin', 'splash', 'whoosh', 'meow', 'woof', 'applause', 'bell',
               'click', 'crash', 'chirp', 'bubble', 'swoosh', 'zap', 'bounce',
               'sparkle', 'drip', 'knock', 'whistle', 'success', 'oops')
NOTES = {'C':0, 'D':2, 'E':4, 'F':5, 'G':7, 'A':9, 'B':11}


def parse_notes(text, limit=256):
    if not isinstance(text, str):
        raise ValueError('Notes are text, like "C D E" or "C4 E4 G4".')
    words = text.split()
    if not words or len(words)>limit:
        raise ValueError(f'Use between 1 and {limit} notes.')
    notes=[]
    for word in words:
        if word.upper() in ('R', 'REST', '-'):
            notes.append(None)
            continue
        match=re.fullmatch(r'([A-Ga-g])([#b]?)([0-8]?)',word)
        if not match:
            raise ValueError('Use note names C D E F G A B, optional # or b and octave 0–8; R is a rest.')
        letter, accidental, octave=match.groups()
        midi=(int(octave or 4)+1)*12+NOTES[letter.upper()]+{'':0,'#':1,'b':-1}[accidental]
        notes.append(midi)
    return notes


def frequency(midi):
    return 440*2**((midi-69)/12)
