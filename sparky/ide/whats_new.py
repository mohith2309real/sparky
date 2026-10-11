# Release notes shown on the Home screen and in the What's new window.
# Newest first. Each release: version, date, title, items (short sentences).

RELEASES = [
    {
        "version": "3.0.0-alpha.5",
        "date": "2026-10-11",
        "title": "Make music, get hints and code together",
        "items": [
            "Songs, chords, five instruments, tempo and rests, with a piano and 27 sounds.",
            "AI hints, challenges and plans, per-project chats and a preview before inserting code.",
            "See exactly what gets sent to AI; use local providers or more compatible presets.",
            "Real Sparky extension commands, three packs and a signed featured catalog.",
            "Preview themes, choose fonts and mascot colors, and share preferences without keys.",
            "Readable text, color-blind syntax, a thicker cursor, read aloud and a left-handed layout.",
            "Hindi and Telugu core controls in beta; lessons and command words stay in English.",
            "Teacher PIN, offline restrictions, checked assignments and named hand-in ZIPs.",
            "Local time on task, optional break reminders and an offline teacher guide.",
        ],
    },
    {
        "version": "3.0.0-alpha.4",
        "date": "2026-10-10",
        "title": "Five worlds to learn, and a home for your creations",
        "items": [
            "Thirty offline lessons with challenges, three hints, stars and world certificates.",
            "Daily challenges, bug hunts, quizzes, achievements and progress reports.",
            "A searchable reference, glossary, line explanations and a side-by-side Python track.",
            "Fifty examples, six project templates and replay for individual tour parts.",
            "Projects on Home with thumbnails, rename, duplicate and move to Trash.",
            "Autosave, crash recovery and saved versions that preserve your newer work.",
            "Project bundles include code, images and sounds; the Assets panel helps you use them.",
            "Share cards and Make an App with your name, icon and fullscreen player.",
        ],
    },
    {
        "version": "3.0.0-alpha.3",
        "date": "2026-10-10",
        "title": "An editor that helps, and a debugger you can see",
        "items": [
            "Auto end, closing pairs, live error marks, hover help and completion with docs.",
            "Drag numbers, pick colors, rename names, format code and fold blocks.",
            "Outline, bookmarks, split editor, minimap, Zen mode and Find in all files.",
            "Live mode re-runs drawings while you type; export colored code as HTML.",
            "Breakpoints, live variables, call stack and watch expressions in the Debug panel.",
            "Run selected lines, filter the console, follow errors to lessons and replay drawings.",
            "Run history, timing, fading line trails and a hint for loops that never wait.",
            "The interactive tour now shows you the Debug panel.",
        ],
    },
    {
        "version": "3.0.0-alpha.2",
        "date": "2026-10-09",
        "title": "Games, shapes, records — and Arduino",
        "items": [
            "Many sprites with emoji costumes, plus when key pressed, when clicked and broadcast.",
            "Shapes, fills, dashed and rainbow pens, backdrops, thought bubbles and speak.",
            "Text with {names} inside, records, ask with buttons, try / oops, save and load.",
            "Record the stage as an animated GIF, or save it as a PNG or SVG.",
            "Sparky works like the Arduino IDE: boards, Upload, Serial Monitor and Plotter.",
            "Sparky for Arduino: write pin 13 on and upload it to a real board.",
            "Friendlier errors that show what you wrote and what to try.",
        ],
    },
    {
        "version": "3.0.0-alpha.1",
        "date": "2026-10-08",
        "title": "A whole new look, and updates that install themselves",
        "items": [
            "Spark 3 design: new fonts, icons, colors and a Home screen.",
            "Four themes: Daylight, Midnight, Candy and High Contrast.",
            "Pause and Step through your program one line at a time.",
            "Stage tools: grid, snapshot to PNG, fullscreen.",
            "An interactive tour that shows you around.",
            "Signed over-the-air updates with automatic rollback.",
            "Kid mode and Pro mode, a native menu bar, and toasts.",
        ],
    },
]


def latest():
    return RELEASES[0]


def notes_for(version):
    for release in RELEASES:
        if release["version"] == version:
            return release
    return None


def pretty_version(version):
    """'3.0.0-alpha.1' -> '3.0 alpha 1'."""
    main, _, pre = version.partition("-")
    parts = main.split(".")
    if len(parts) == 3 and parts[2] == "0":
        main = ".".join(parts[:2])
    if pre:
        name, _, num = pre.partition(".")
        return f"{main} {name} {num}".strip()
    return main
