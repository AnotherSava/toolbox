from tools.fb_strikethrough.strikethrough import to_strikethrough

S = "\u0336"


def test_basic_conversion():
    assert to_strikethrough("hello") == f"h{S}e{S}l{S}l{S}o{S}"


def test_preserves_spaces():
    result = to_strikethrough("hello world")
    assert result == f"h{S}e{S}l{S}l{S}o{S} w{S}o{S}r{S}l{S}d{S}"


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


def test_tabs_preserved():
    result = to_strikethrough("a\tb")
    assert result == f"a{S}\tb{S}"
