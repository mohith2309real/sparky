"""Bounded, offline lesson checks and local learning progress (no Qt needed)."""
import datetime
import html
import math
import time

from ..lang import Interpreter, Runtime, SparkyError, parse
from ..lang.ast_nodes import Node, Use
from .learning_data import LESSONS, WORLDS
from .projects import atomic_write, read_json, user_root
import json


def walk(value):
    if isinstance(value, Node):
        yield value
        for child in vars(value).values():
            yield from walk(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from walk(child)
    elif isinstance(value, dict):
        for child in value.values():
            yield from walk(child)


class Capture(Runtime):
    def __init__(self, answers=(), events=()):
        super().__init__()
        self.answers = iter(answers)
        self.event_queue = list(events)
        self.polls = 0
        self.output, self.lines, self.shapes, self.stamps = [], [], [], []

    def say(self, text):
        self.output.append(text)

    def ask(self, prompt):
        return next(self.answers, None)

    def line(self, x1, y1, x2, y2, color, width):
        self.lines.append((x1, y1, x2, y2))

    def shape(self, points, closed, pen, fill):
        self.shapes.append((points, fill))

    def stamp_sprite(self, snapshot):
        self.stamps.append(snapshot)

    def clear(self):
        self.lines.clear()
        self.shapes.clear()
        self.stamps.clear()

    def events(self):
        self.polls += 1
        if self.event_queue and self.polls % 40 == 0:
            return [self.event_queue.pop(0)]
        return []

    def wants_events(self):
        return bool(self.event_queue)


def close_pair(got, wanted):
    return all(math.isclose(a, b, abs_tol=0.01) for a, b in zip(got, wanted))


class CheckInterpreter(Interpreter):
    # Animation speed must not change how many logical pen strokes get checked.
    @property
    def speed(self):
        return 10

    @speed.setter
    def speed(self, value):
        pass


def check_program(lesson, source, cancelled=lambda: False):
    """Try real inputs/events and inspect results, without touching the live stage/files."""
    if len(source) > 100000:
        return False, 'Try checking a smaller program (under 100,000 characters).'
    try:
        program = parse(source)
        nodes = list(walk(program))
        if any(isinstance(n, Use) for n in nodes):
            return False, 'For this lesson, put your code in one tab instead of using another file.'
        kinds = {type(n).__name__ for n in nodes}
        missing = set(lesson['requires']) - kinds
        if missing:
            return False, 'Use the idea this lesson teaches. ' + lesson['explain']
        checks = lesson['checks']
        if 'shape_kinds' in checks and not set(checks['shape_kinds']).issubset(
                {n.kind for n in nodes if type(n).__name__ == 'Shape'}):
            return False, 'Use each shape named in the challenge: ' + ', '.join(checks['shape_kinds']) + '.'
        for answers, output in checks.get('cases', [((), checks.get('output'))]):
            runtime = Capture(answers, checks.get('events', ()))
            interpreter = CheckInterpreter(program, runtime, source=source)
            started = time.monotonic()
            generator = interpreter.run()
            try:
                for ticks, tick in enumerate(generator):
                    if cancelled():
                        return False, 'Check cancelled. Your code is still here.'
                    if ticks > 50000 or time.monotonic() - started > 3:
                        return False, 'This check took too long. Check that your loops can finish.'
                    if tick[0] == 'wait' and tick[-1] is None:
                        time.sleep(min(max(tick[1], 0), 0.001))
            finally:
                generator.close()
            if output is not None and runtime.output != output:
                expected = ' / '.join(output)
                return False, f'Try again. With the test answers {list(answers)}, the console should say: {expected}'
            if 'lines' in checks and len(runtime.lines) != checks['lines']:
                return False, f"Your drawing needs {checks['lines']} pen lines; it has {len(runtime.lines)}."
            if 'lengths' in checks:
                lengths = [math.hypot(x2-x1, y2-y1) for x1,y1,x2,y2 in runtime.lines]
                if len(lengths) != len(checks['lengths']) or not close_pair(lengths, checks['lengths']):
                    return False, 'Check the lengths of your drawn sides.'
            if 'position' in checks and not close_pair([interpreter.x, interpreter.y], checks['position']):
                return False, 'Check where Sparky ends up. ' + lesson['goal']
            if 'shapes' in checks and len(runtime.shapes) != checks['shapes']:
                return False, 'Check how many shapes your program draws.'
            if 'filled' in checks and sum(bool(fill) for _, fill in runtime.shapes) != checks['filled']:
                return False, 'Give each shape a fill color.'
            if 'stamps' in checks and len(runtime.stamps) != checks['stamps']:
                return False, 'Check how many stamps your program makes.'
            for key, value in checks.get('variables', {}).items():
                if interpreter.globals.get(key) != value:
                    return False, f'Check the value stored in {key}.'
            for name, position in checks.get('sprites', {}).items():
                sprite = interpreter.sprites.get(name)
                if sprite is None or not close_pair([sprite.x, sprite.y], position):
                    return False, f'Check where the {name} sprite ends up.'
        return True, 'You did it! Your program passed every check.'
    except SparkyError as error:
        return False, error.pretty()
    except (ValueError, TypeError, OverflowError, RecursionError) as error:
        return False, 'The checker could not finish this program: ' + str(error)


class Progress:
    def __init__(self, path=None):
        self.path = path or user_root() / '.learning.json'
        self.data = read_json(self.path, {})
        for key in ('stars', 'hints'):
            if not isinstance(self.data.get(key), dict):
                self.data[key] = {}
        if not isinstance(self.data.get('runs'), int):
            self.data['runs'] = 0

    def save(self):
        atomic_write(self.path, json.dumps(self.data, ensure_ascii=False, indent=2))

    def stars(self, key):
        value = self.data['stars'].get(key, 0)
        return max(0, min(3, value)) if isinstance(value, int) else 0

    def hint(self, key):
        value = self.data['hints'].get(key, 0)
        level = min(3, value + 1) if isinstance(value, int) else 1
        self.data['hints'][key] = level
        self.save()
        return level

    def finished_world(self, world):
        return all(self.stars(l['id']) for l in LESSONS if l['world'] == world)

    def complete(self, lesson):
        was_done = self.finished_world(lesson['world'])
        hints = self.data['hints'].get(lesson['id'], 0)
        hints = hints if isinstance(hints, int) else 0
        stars = max(1, 3 - min(2, hints))
        self.data['stars'][lesson['id']] = max(self.stars(lesson['id']), stars)
        self.data['last_lesson'] = lesson['id']
        self.save()
        return not was_done and self.finished_world(lesson['world'])

    def record_run(self):
        self.data['runs'] += 1
        self.save()

    def next_lesson(self):
        return next((l for l in LESSONS if not self.stars(l['id'])), LESSONS[-1])

    def badges(self):
        result = []
        if self.data['runs'] or any(self.stars(l['id']) for l in LESSONS):
            result.append('First program')
        if self.stars('first-game'):
            result.append('Game maker')
        if self.data['runs'] >= 100:
            result.append('100 runs')
        result.extend(title + ' explorer' for key,title,_ in WORLDS if self.finished_world(key))
        return result

    def report(self, name):
        rows = ''.join('<tr><td>'+html.escape(l['title'])+'</td><td>'+str(self.stars(l['id']))+'/3</td></tr>'
                       for l in LESSONS)
        badges = ', '.join(self.badges()) or 'Keep exploring to earn your first badge.'
        return ('<!doctype html><html lang="en"><meta charset="utf-8"><title>Sparky progress</title>'
                '<style>body{font:18px system-ui;max-width:850px;margin:40px auto;color:#141413}'
                'td{padding:6px 18px;border-bottom:1px solid #ddd}</style><h1>'+html.escape(name)+
                '’s Sparky progress</h1><p>'+datetime.date.today().isoformat()+
                ' · Stored on this computer only</p><p>'+html.escape(badges)+
                '</p><p>Programs run: '+str(self.data['runs'])+'</p><table>'+rows+'</table></html>')


def daily_lesson(day=None):
    day = day or datetime.date.today()
    return LESSONS[day.toordinal() % len(LESSONS)]
