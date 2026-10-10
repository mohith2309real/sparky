"""Thirty offline lessons: six stops in each of five worlds."""
WORLDS = [('draw', 'Draw', 'Make marks, shapes and pictures.'),
          ('loops', 'Loops', 'Make a small program do a lot.'),
          ('talk', 'Talk and Ask', 'Give your programs a voice.'),
          ('logic', 'Lists and Logic', 'Remember things and make choices.'),
          ('games', 'Games', 'Bring sprites and events together.')]

# id, title, explanation, goal, example, checks, required language concepts
SPECS = [
 ('first-line', 'Draw with the pen', 'move walks forward; the pen draws as you go.',
  'Draw one line 60 steps upwards.', 'move 60\n', {'lines': 1, 'position': [0, 60]}, ['Move']),
 ('square', 'A square', 'Four equal sides and four right turns close a square.',
  'Use a repeat loop to draw a square with sides of 80.', 'repeat 4 times\n  move 80\n  turn 90\nend\n', {'lines': 4, 'position': [0, 0], 'lengths': [80]*4}, ['RepeatTimes']),
 ('pen-up', 'Travel without drawing', 'pen up lets you travel without leaving a trail.',
  'Travel 40 upwards without drawing, then draw a line 60 upwards.', 'pen up\nmove 40\npen down\nmove 60\n', {'lines': 1, 'position': [0, 100], 'lengths': [60]}, ['Pen']),
 ('shapes', 'Shapes everywhere', 'Sparky has circle, rectangle and star commands. fill color fills their insides.',
  'Draw three filled shapes: a circle, rectangle and star.', 'fill color "yellow"\ncircle 30\nrectangle 60 by 40\nstar 5 points 40\n', {'shapes': 3, 'filled': 3, 'shape_kinds': ['circle', 'rectangle', 'star']}, ['Shape', 'Fill']),
 ('coordinates', 'Find your place', 'x moves right; y moves up. The middle is 0 0.',
  'With the pen up, go to x 100, y 50 and stamp once.', 'pen up\ngoto 100 50\nstamp\n', {'position': [100, 50], 'stamps': 1, 'lines': 0}, ['Goto']),
 ('star-art', 'Star artist', 'A five-pointed star turns 144 degrees at every corner.',
  'Draw a five-pointed star with five lines of 100.', 'repeat 5 times\n  move 100\n  turn 144\nend\n', {'lines': 5, 'lengths': [100]*5, 'position': [0, 0]}, ['RepeatTimes']),
 ('repeat', 'Loops!', 'repeat runs its body a fixed number of times. end closes the loop.',
  'Use repeat to say Go! three times.', 'repeat 3 times\n  say "Go!"\nend\n', {'output': ['Go!']*3}, ['RepeatTimes']),
 ('count', 'Count up', 'for counts with a named variable that changes each time.',
  'Print the numbers 1 through 5, one on each line.', 'for i from 1 to 5\n  say i\nend\n', {'output': ['1','2','3','4','5']}, ['ForRange']),
 ('countdown', 'Countdown', 'A negative step counts backwards.',
  'Print 3, 2, 1, then Lift off!', 'for i from 3 to 1 by -1\n  say i\nend\nsay "Lift off!"\n', {'output': ['3','2','1','Lift off!']}, ['ForRange']),
 ('until', 'Keep trying', 'repeat until checks a condition before each turn.',
  'Start score at 0 and add 2 until it reaches 10. Print 10.', 'set score to 0\nrepeat until score = 10\n  change score by 2\nend\nsay score\n', {'output':['10'], 'variables':{'score':10}}, ['RepeatUntil']),
 ('teach', 'Teach new tricks', 'teach names a reusable recipe; do runs it.',
  'Teach a square command, then use it to draw two squares.', 'teach square\n  repeat 4 times\n    move 40\n    turn 90\n  end\nend\ndo square\ndo square\n', {'lines':8, 'lengths':[40]*8}, ['Teach','Do']),
 ('loop-bug', 'Bug hunt: one missing side', 'A square needs four sides. Read the repeat count carefully.',
  'Fix the starter so it draws a square, not three sides.', 'repeat 4 times\n  move 60\n  turn 90\nend\n', {'lines':4, 'position':[0,0], 'lengths':[60]*4}, ['RepeatTimes']),
 ('hello', 'Say hello!', 'Quotes keep words together. say sends them to the console.',
  'Print Hello, world! exactly once.', 'say "Hello, world!"\n', {'output':['Hello, world!']}, ['Say']),
 ('ask', 'Ask questions', 'ask waits for an answer and stores it into a named variable.',
  'Ask for a name, then greet that person with Hello, name!', 'ask "Your name?" into name\nsay "Hello, {name}!"\n', {'cases':[(['Ada'],['Hello, Ada!']),(['Ravi'],['Hello, Ravi!'])]}, ['Ask']),
 ('numbers', 'Ask for a number', 'ask number accepts numbers so you can do maths with the answer.',
  'Ask for a number and print its double.', 'ask number "A number?" into n\nsay n * 2\n', {'cases':[(['7'],['14']),(['3'],['6'])]}, ['Ask']),
 ('memory', 'Remember things', 'set makes a variable; change adds to it.',
  'Set score to 5, add 3, then print the score.', 'set score to 5\nchange score by 3\nsay score\n', {'output':['8'], 'variables':{'score':8}}, ['SetVar','ChangeVar']),
 ('templates', 'Words with values', 'Braces inside text insert a variable’s current value.',
  'Make name be Sparky and print I am Sparky.', 'set name to "Sparky"\nsay "I am {name}."\n', {'output':['I am Sparky.']}, ['Template']),
 ('quote-bug', 'Bug hunt: close the quote', 'Every opening quote needs a closing quote.',
  'Fix the broken starter so it prints Fixed!', 'say "Fixed!"\n', {'output':['Fixed!']}, ['Say']),
 ('choices', 'Make choices', 'if picks which branch runs; else handles the other case.',
  'Ask for a number. Say Big for numbers over 10, otherwise Small.', 'ask number "Number?" into n\nif n > 10 then\n  say "Big"\nelse\n  say "Small"\nend\n', {'cases':[(['12'],['Big']),(['3'],['Small'])]}, ['If']),
 ('lists', 'Lists', 'A list holds many values in order. Sparky counts items from 1.',
  'Make a pets list containing cat, dog, fish. Print the second pet.', 'set pets to ["cat", "dog", "fish"]\nsay item 2 of pets\n', {'output':['dog'], 'variables':{'pets':['cat','dog','fish']}}, ['ListLit','Index']),
 ('each', 'Visit every item', 'for each gives every item its own turn.',
  'Use a loop to print red, green and blue.', 'set colors to ["red", "green", "blue"]\nfor each shade in colors\n  say shade\nend\n', {'output':['red','green','blue']}, ['ForEach']),
 ('records', 'Meet a record', 'A record groups named facts about one thing.',
  'Make a pet record with name Rex and age 3. Print Rex.', 'set pet to {name: "Rex", age: 3}\nsay name of pet\n', {'output':['Rex'], 'variables':{'pet':{'name':'Rex','age':3}}}, ['RecordLit','Field']),
 ('answers', 'Commands that answer', 'give back returns a value that other code can use.',
  'Teach double n, then print double(6).', 'teach double n\n  give back n * 2\nend\nsay double(6)\n', {'output':['12']}, ['Teach','Return','Call']),
 ('logic-bug', 'Bug hunt: the wrong branch', 'Try both sides of a condition. A useful check should work for more than one input.',
  'Fix the starter so scores of at least 5 say Win; lower scores say Try again.', 'ask number "Score?" into score\nif score >= 5 then\n  say "Win"\nelse\n  say "Try again"\nend\n', {'cases':[(['5'],['Win']),(['4'],['Try again']),(['8'],['Win'])]}, ['If']),
 ('sprites', 'Meet your sprites', 'make sprite gives a character its own position and costume.',
  'Make a rocket sprite, then move it to x 50, y 20 without drawing.', 'make sprite rocket with costume "🚀"\ntell rocket\n  pen up\n  goto 50 20\nend\n', {'sprites':{'rocket':[50,20]}}, ['MakeSprite','Tell']),
 ('messages', 'Send a message', 'broadcast starts matching when message scripts.',
  'Broadcast go; a message handler should say Ready!', 'when message "go"\n  say "Ready!"\nend\nbroadcast "go"\n', {'output':['Ready!']}, ['When','Broadcast']),
 ('keyboard', 'Press to play', 'A key event runs only when that key is pressed. Click the stage before using keys.',
  'Say Jump! when Space is pressed. The checker presses Space for you.', 'when key "space" pressed\n  say "Jump!"\nend\n', {'events':[('key','space')], 'output':['Jump!']}, ['When']),
 ('clicks', 'Click for points', 'A stage click can change a score. Set it before the first click.',
  'Start score at 0. Every stage click adds 1 and says the score. The checker clicks twice.', 'set score to 0\nwhen stage clicked\n  change score by 1\n  say score\nend\n', {'events':[('stage_click',0,0),('stage_click',10,10)], 'output':['1','2']}, ['When','ChangeVar']),
 ('memory-game', 'Keep your best score', 'save and load let a game remember values. The checker uses temporary memory.',
  'Save a score of 12 as best, load it into best, and print it.', 'set score to 12\nsave score as "best"\nload "best" into best\nsay best\n', {'output':['12'], 'variables':{'best':12}}, ['Save','Load']),
 ('first-game', 'Your first game', 'Combine a sprite, a key event and a score. Small pieces make a game.',
  'Make a rocket. On Space, move it up 20, add 1 to score and say the score. The checker presses twice.', 'make sprite rocket with costume "🚀"\nset score to 0\nwhen key "space" pressed\n  tell rocket\n    pen up\n    move 20\n  end\n  change score by 1\n  say score\nend\n', {'events':[('key','space'),('key','space')], 'output':['1','2'], 'sprites':{'rocket':[0,40]}}, ['MakeSprite','When','Tell']),
]

LESSONS = []
for index, (key, title, explain, goal, code, checks, requires) in enumerate(SPECS):
    world = WORLDS[index // 6][0]
    starter = '# ' + goal + '\n'
    if key == 'loop-bug':
        starter = code.replace('repeat 4', 'repeat 3')
    elif key == 'quote-bug':
        starter = 'say "Fixed!\n'
    elif key == 'logic-bug':
        starter = code.replace('score >= 5', 'score > 5')
    LESSONS.append(dict(id=key, world=world, title=title, explain=explain, goal=goal, code=code,
                        starter=starter, checks=checks, requires=requires,
                        hints=[explain, 'Try the structure in the example, then check each number and word against the goal.',
                               'One solution:\n' + code]))
BY_ID = {lesson['id']: lesson for lesson in LESSONS}
GLOSSARY = {
    'algorithm':'A set of steps for solving a problem.', 'bug':'A mistake that makes a program behave differently from your plan.',
    'condition':'A question with a true or false answer.', 'debug':'Find a bug, understand it, and fix it.',
    'event':'Something that happens, like a click or a key press.', 'function':'A named recipe that can take inputs and give back an answer.',
    'list':'Several values kept together in order.', 'loop':'Instructions that repeat.', 'record':'Named facts kept together.',
    'sprite':'A character on the stage.', 'variable':'A name for a value your program remembers.',
}
QUIZZES = [
    ('say 2 + 3', ['5', '23', '2 + 3'], 0, 'Two numbers are added.'),
    ('repeat 2 times\n  say "Hi"\nend', ['Hi once', 'Hi twice', 'Nothing'], 1, 'The body runs two times.'),
    ('set n to 3\nchange n by 2\nsay n', ['3', '2', '5'], 2, 'change adds 2 to the current value.'),
    ('set pets to ["cat", "dog"]\nsay item 1 of pets', ['dog', 'cat', '1'], 1, 'Sparky list positions start at 1.'),
    ('if 3 > 5 then\n  say "A"\nelse\n  say "B"\nend', ['A', 'B', 'A and B'], 1, '3 > 5 is false, so else runs.'),
]
