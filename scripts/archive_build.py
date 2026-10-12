"""Preserve earlier build outputs instead of deleting them before rebuilding."""
import datetime
import sys
import uuid
from pathlib import Path
root=Path(__file__).resolve().parent.parent
archive=root/'build'/'archive'/(datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6])
for argument in sys.argv[1:]:
    path=(root/argument).resolve()
    if not path.is_relative_to(root): raise ValueError('Build outputs must be inside the repository.')
    if path.exists():
        target=archive/path.relative_to(root); target.parent.mkdir(parents=True,exist_ok=True)
        path.rename(target); print('Previous build saved:',target.relative_to(root))
