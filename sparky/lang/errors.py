# Kid-friendly errors for Sparky.
# Every error carries a line number and speaks plain English —
# no tracebacks, no jargon, and a "did you mean...?" when we can guess.

import difflib


class SparkyError(Exception):
    def __init__(self, message, line=None):
        super().__init__(message)
        self.message = message
        self.line = line

    def pretty(self):
        where = f"Line {self.line}: " if self.line else ""
        return f"Oops! {where}{self.message}"


def did_you_mean(word, choices):
    """Return a friendly suggestion string like ' Did you mean "move"?' or ''."""
    matches = difflib.get_close_matches(word, list(choices), n=1, cutoff=0.7)
    if matches:
        return f' Did you mean "{matches[0]}"?'
    return ""
