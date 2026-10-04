import pytest
import config
from core.regex_utils import (
    compile_pattern,
    safe_search,
    safe_subn,
    matches_empty,
    PatternError,
    RegexTimeoutError,
    HAS_REGEX_MODULE,
)



def test_compile_pattern_literal_mode_escapes_metacharacters():
    # In literal mode, 'a.b' should not match 'axb', only 'a.b'
    pattern = compile_pattern("a.b", regex_mode=False, case_sensitive=True)
    assert safe_search(pattern, "a.b") is not None
    assert safe_search(pattern, "axb") is None


def test_compile_pattern_regex_mode():
    pattern = compile_pattern("a.b", regex_mode=True, case_sensitive=True)
    assert safe_search(pattern, "axb") is not None
    assert safe_search(pattern, "a.b") is not None


def test_compile_pattern_case_sensitivity():
    pattern_ci = compile_pattern("hello", regex_mode=False, case_sensitive=False)
    assert safe_search(pattern_ci, "HELLO") is not None

    pattern_cs = compile_pattern("hello", regex_mode=False, case_sensitive=True)
    assert safe_search(pattern_cs, "HELLO") is None


def test_compile_pattern_too_long(monkeypatch):
    monkeypatch.setattr(config, "MAX_REGEX_PATTERN_LENGTH", 10)
    with pytest.raises(PatternError, match="exceeds maximum allowed limit"):
        compile_pattern("a" * 11, regex_mode=True)


def test_compile_pattern_invalid_regex():
    with pytest.raises(PatternError, match="Invalid regular expression"):
        compile_pattern("(", regex_mode=True)


def test_matches_empty():
    pattern_star = compile_pattern("a*", regex_mode=True)
    assert matches_empty(pattern_star) is True

    pattern_plus = compile_pattern("a+", regex_mode=True)
    assert matches_empty(pattern_plus) is False


@pytest.mark.skipif(not HAS_REGEX_MODULE, reason="PyPI 'regex' package is required for timeout guard tests")
def test_catastrophic_backtracking_timeout(monkeypatch):
    monkeypatch.setattr(config, "REGEX_TIMEOUT_SECONDS", 0.1)
    # Classic catastrophic backtracking regex
    pattern = compile_pattern(r"(a+)+$", regex_mode=True)
    evil_text = "a" * 35 + "!"

    with pytest.raises(RegexTimeoutError, match="timed out"):
        safe_search(pattern, evil_text)

    with pytest.raises(RegexTimeoutError, match="timed out"):
        safe_subn(pattern, "x", evil_text)

