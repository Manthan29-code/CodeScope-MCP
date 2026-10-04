from typing import Optional, Tuple, Any
import config

try:
    import regex
    HAS_REGEX_MODULE = True
except ModuleNotFoundError:
    import re as regex
    HAS_REGEX_MODULE = False


class PatternError(ValueError):
    """Raised when a regular expression or search pattern is invalid or too long."""
    pass


class RegexTimeoutError(PatternError):
    """Raised when a regex operation exceeds the configured timeout."""
    pass



def compile_pattern(query: str, *, regex_mode: bool = False, case_sensitive: bool = True) -> regex.Pattern:
    """
    Compiles a string or regular expression pattern with safety guards on pattern length.
    
    Args:
        query: String or regex query.
        regex_mode: If True, compiles as regex; if False, escapes query for literal match.
        case_sensitive: Whether match should be case sensitive.
        
    Returns:
        Compiled regex.Pattern object.
    """
    if len(query) > config.MAX_REGEX_PATTERN_LENGTH:
        raise PatternError(
            f"Pattern length ({len(query)}) exceeds maximum allowed limit MAX_REGEX_PATTERN_LENGTH ({config.MAX_REGEX_PATTERN_LENGTH})."
        )

    flags = 0 if case_sensitive else regex.IGNORECASE
    pattern_str = query if regex_mode else regex.escape(query)

    try:
        return regex.compile(pattern_str, flags)
    except (regex.error, Exception) as e:
        raise PatternError(f"Invalid regular expression pattern: {e}")


def safe_search(compiled: Any, text: str) -> Optional[Any]:
    """
    Performs search on text with a timeout guard if supported by the regex backend.
    """
    if HAS_REGEX_MODULE:
        timeout = getattr(config, "REGEX_TIMEOUT_SECONDS", 2.0)
        try:
            return compiled.search(text, timeout=timeout)
        except TimeoutError:
            raise RegexTimeoutError(f"Regex search operation timed out after {timeout} seconds.")
        except Exception as e:
            if "timeout" in str(e).lower():
                raise RegexTimeoutError(f"Regex search operation timed out after {timeout} seconds.")
            raise
    return compiled.search(text)


def safe_subn(compiled: Any, repl: Any, text: str) -> Tuple[str, int]:
    """
    Performs regex subn substitution on text with a timeout guard if supported by the regex backend.
    """
    if HAS_REGEX_MODULE:
        timeout = getattr(config, "REGEX_TIMEOUT_SECONDS", 2.0)
        try:
            return compiled.subn(repl, text, timeout=timeout)
        except TimeoutError:
            raise RegexTimeoutError(f"Regex replacement operation timed out after {timeout} seconds.")
        except Exception as e:
            if "timeout" in str(e).lower():
                raise RegexTimeoutError(f"Regex replacement operation timed out after {timeout} seconds.")
            raise
    return compiled.subn(repl, text)



def matches_empty(compiled: regex.Pattern) -> bool:
    """
    Returns True if the compiled pattern matches an empty string.
    """
    try:
        match = safe_search(compiled, "")
        return match is not None
    except Exception:
        return False
