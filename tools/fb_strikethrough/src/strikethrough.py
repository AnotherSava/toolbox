COMBINING_LONG_STROKE = "\u0336"


def strip_strikethrough(text: str) -> str:
    """Remove all U+0336 combining characters from text."""
    return text.replace(COMBINING_LONG_STROKE, "")


def to_strikethrough(text: str) -> str:
    """Convert text to Unicode strikethrough by inserting U+0336 after each character.

    Spaces are struck through too, creating a continuous line.
    Newlines are preserved as-is (striking them has no visual effect).
    Already-struck text is returned unchanged (idempotent).
    """
    if not text:
        return text

    result = []
    i = 0
    while i < len(text):
        char = text[i]
        result.append(char)

        # Don't strike newlines — no visual effect
        if char == "\n":
            i += 1
            continue

        # Skip any existing U+0336 sequences after this character
        if i + 1 < len(text) and text[i + 1] == COMBINING_LONG_STROKE:
            while i + 1 < len(text) and text[i + 1] == COMBINING_LONG_STROKE:
                i += 1
            result.append(COMBINING_LONG_STROKE)
            i += 1
        else:
            result.append(COMBINING_LONG_STROKE)
            i += 1

    return "".join(result)
