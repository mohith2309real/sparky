# Release notes shown on the Home screen and in the What's new window.
# Newest first. Each release: version, date, title, items (short sentences).

RELEASES = [
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
