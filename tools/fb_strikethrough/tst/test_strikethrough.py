from fb_strikethrough.strikethrough import strip_strikethrough, to_strikethrough

S = "\u0336"


def test_basic_conversion():
    assert to_strikethrough("hello") == f"h{S}e{S}l{S}l{S}o{S}"


def test_strikes_spaces():
    result = to_strikethrough("hello world")
    assert result == f"h{S}e{S}l{S}l{S}o{S} {S}w{S}o{S}r{S}l{S}d{S}"


def test_preserves_newlines():
    result = to_strikethrough("line1\nline2")
    assert result == f"l{S}i{S}n{S}e{S}1{S}\nl{S}i{S}n{S}e{S}2{S}"


def test_empty_string():
    assert to_strikethrough("") == ""


def test_idempotent():
    once = to_strikethrough("hello")
    twice = to_strikethrough(once)
    assert once == twice


def test_unicode_accented():
    result = to_strikethrough("café")
    assert result == f"c{S}a{S}f{S}é{S}"


def test_strikes_tabs():
    result = to_strikethrough("a\tb")
    assert result == f"a{S}\t{S}b{S}"


def test_idempotent_with_multiple_strokes():
    """Already-struck text with multiple U+0336 gets normalized to one."""
    mangled = f"h{S}{S}{S}e{S}{S}{S}"
    result = to_strikethrough(mangled)
    assert result == f"h{S}e{S}"


def test_strip_basic():
    assert strip_strikethrough(f"h{S}e{S}l{S}l{S}o{S}") == "hello"


def test_strip_empty():
    assert strip_strikethrough("") == ""


def test_strip_no_strokes():
    assert strip_strikethrough("hello") == "hello"


def test_strip_multiple_strokes():
    """Strips even mangled text with multiple U+0336 per character."""
    mangled = f"h{S}{S}{S}e{S}{S}{S}l{S}l{S}o{S}"
    assert strip_strikethrough(mangled) == "hello"


def test_strip_with_spaces():
    struck = f"h{S}i{S} {S}y{S}o{S}u{S}"
    assert strip_strikethrough(struck) == "hi you"


def test_strip_then_restrike():
    """Full round-trip: strip mangled text, then re-apply cleanly."""
    mangled = f"h{S}{S}{S}e{S}{S}{S}l{S}{S}l{S}{S}o{S}{S}"
    clean = strip_strikethrough(mangled)
    assert clean == "hello"
    result = to_strikethrough(clean)
    assert result == f"h{S}e{S}l{S}l{S}o{S}"
