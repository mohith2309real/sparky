NAME='Shapes+'
AUTHOR='Mohith'
DESCRIPTION='Real triangle and hexagon commands with a side length.'
def register(api):
    api.add_command('triangle',('side',),'repeat 3 times\nmove side\nturn 120\nend', 'Draw an equilateral triangle.')
    api.add_command('hexagon',('side',),'repeat 6 times\nmove side\nturn 60\nend', 'Draw a regular hexagon.')
    api.add_blocks('SHAPES+', 'accent2', [('triangle','triangle 80','Draw a triangle.'),('hexagon','hexagon 50','Draw a hexagon.')])
