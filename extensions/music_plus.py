NAME='Music+'
AUTHOR='Mohith'
DESCRIPTION='A fanfare and a warm three-note chime.'
def register(api):
    api.add_command('fanfare',(),'instrument "piano"\nplay song "C4 E4 G4 C5" for 0.15', 'Play a short celebration.')
    api.add_command('chime',(),'instrument "xylophone"\nplay chord "C5 E5 G5" for 0.4', 'Play a three-note chord.')
    api.add_blocks('MUSIC+', 'accent3',[('fanfare','fanfare','Play a celebration.'),('chime','chime','Play a chord.')])
