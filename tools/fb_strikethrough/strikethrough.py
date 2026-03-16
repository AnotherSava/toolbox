COMBINING_LONG_STROKE = "\u0336"


def to_strikethrough(text: str) -> str:
    """Convert text to Unicode strikethrough by inserting U+0336 after each visible character."""
    if not text:
        return text

    result = []
    i = 0
    while i < len(text):
        char = text[i]
        result.append(char)

        if char.isspace():
            i += 1
            continue

        # Check if next char is already U+0336 — skip to avoid double-striking
        if i + 1 < len(text) and text[i + 1] == COMBINING_LONG_STROKE:
            result.append(text[i + 1])
            i += 2
        else:
            result.append(COMBINING_LONG_STROKE)
            i += 1

    return "".join(result)
