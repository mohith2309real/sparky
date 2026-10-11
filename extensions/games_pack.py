NAME='Games'
AUTHOR='Mohith'
DESCRIPTION='Teleport without drawing and celebrate a win.'
def register(api):
    api.add_command('teleport',('x_pos','y_pos'),'pen up\ngoto x_pos y_pos', 'Move without a pen trail.')
    api.add_command('win',(),'say "You win!"\nplay "tada"', 'Announce a win.')
    api.add_blocks('GAMES PACK','accent',[('teleport','teleport 100 50','Move anywhere.'),('win','win','Celebrate a win.')])
