# Sparky in the classroom

Sparky lessons, coding, assignment checks and hand-ins work offline. No student account is needed. AI is optional and uses the provider configured on this computer.

## Start a class

Open Settings → Classroom. Choose a teacher PIN (4–12 digits), enable Classroom mode, and choose whether to hide AI and disable extensions. Settings will ask for the PIN next time. Keep the PIN somewhere you control. This is a local app lock; someone who can edit Sparky's settings files can bypass it. It is not an operating-system security boundary.

Turn on Offline mode in Settings → Privacy to pause AI requests, update checks, extension catalogs and Arduino downloads. Installed tools and built-in lessons keep working. Set up any Arduino board packages before the class.

## Give an assignment

Use File → Open assignment and choose `first_square.sparkytask` from Examples → Assignments. Read the instructions, open the starter in a new tab, and use Check my work. Checks run separately from the student's stage with time, output and drawing limits. Students can retry without losing their code.

To make another assignment, copy the example and edit its JSON fields:

```json
{
  "product": "sparky-task", "schema": 1,
  "title": "Say hello", "instructions": "Print Hello, class!",
  "starter": "say \"Hello\"\n",
  "requires": ["Say"], "checks": {"output": ["Hello, class!"]}
}
```

`requires` names syntax nodes, such as Say, RepeatTimes, Shape and Fill. Use an empty list if the solution may use any commands. Built-in commands work in checks; custom extension commands are not checked.

Supported checks: output (exact text lines), cases (pairs of answers and expected output), lines (pen-stroke count), lengths (one length per pen stroke), position (final x,y), shapes, filled, stamps, variables (expected names and values), sprites (names and x,y positions), shape_kinds (required shape commands), and events (key, click or stage_click). Drawing coordinates allow a 0.01 tolerance. Each check is limited to three seconds; long-running interactive games need a small test event sequence. File imports are disabled inside checks.

## Collect work

Use File → Hand in, enter the learner's name, and save a ZIP. It contains the current editor text as `main.spark`, `submission.json` with the name, assignment, local date and cumulative time, and supported project code and assets. Hidden files, local chat history and symbolic links are excluded. The ZIP stays on this computer until you share it yourself. Open `main.spark` in Sparky to review; keep its assets beside it. Hand-ins include student code, so review it before running it.

## Time and breaks

Settings → Classroom shows cumulative time on task for this computer, not an individual learner. Time counts while the workspace is active and pauses after five minutes without input. You can turn tracking off. Optional break reminders default to 20 minutes and can be changed to 5–60 minutes. The local activity file stores only a seconds count; it does not collect browsing or send analytics.

For shared computers, separate operating-system profiles keep each learner's projects and progress separate. Hindi and Telugu currently translate core controls; lessons and Sparky command words remain in English.
