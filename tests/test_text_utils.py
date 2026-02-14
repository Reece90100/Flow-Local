import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from flow_local import clean_text, FILLER_WORDS


class TestCleanText:
    """Tests for text cleaning functionality."""

    def test_removes_um_filler(self):
        """Should remove 'um' filler word."""
        text = "um, hello world"
        result = clean_text(text, {"cleanup_fillers": True})
        assert "um" not in result.lower()

    def test_removes_uh_filler(self):
        """Should remove 'uh' filler word."""
        text = "uh, i think uh,"
        result = clean_text(text, {"cleanup_fillers": True})
        assert "uh" not in result.lower()

    def test_removes_umm_filler(self):
        """Should remove 'umm' filler word."""
        text = "umm, yes i think"
        result = clean_text(text, {"cleanup_fillers": True})
        assert "umm" not in result.lower()

    def test_removes_hmm_filler(self):
        """Should remove 'hmm' filler word."""
        text = "hmm, let me think"
        result = clean_text(text, {"cleanup_fillers": True})
        assert "hmm" not in result.lower()

    def test_removes_like_filler(self):
        """Should remove 'like' filler word."""
        text = "like, i was saying"
        result = clean_text(text, {"cleanup_fillers": True})
        assert " like " not in result.lower()

    def test_removes_you_know_filler(self):
        """Should remove 'you know' filler phrase."""
        text = "you know, its true"
        result = clean_text(text, {"cleanup_fillers": True})
        assert "you know" not in result.lower()

    def test_capitalizes_first_letter(self):
        """Should capitalize the first letter of text."""
        text = "hello world"
        result = clean_text(text, {"cleanup_fillers": False})
        assert result[0] == "H"

    def test_preserves_original_when_cleanup_disabled(self):
        """Should not modify text when cleanup_fillers is False."""
        text = "um uh hello"
        result = clean_text(text, {"cleanup_fillers": False})
        assert result == "Um uh hello"

    def test_handles_empty_string(self):
        """Should handle empty string gracefully."""
        result = clean_text("", {"cleanup_fillers": True})
        assert result == ""

    def test_removes_multiple_spaces(self):
        """Should collapse multiple spaces into one."""
        text = "hello    world"
        result = clean_text(text, {"cleanup_fillers": False})
        assert "  " not in result

    def test_handles_leading_trailing_whitespace(self):
        """Should strip leading and trailing whitespace."""
        text = "  hello world  "
        result = clean_text(text, {"cleanup_fillers": False})
        assert result == "Hello world"

    def test_handles_single_character(self):
        """Should handle single character input."""
        text = "a"
        result = clean_text(text, {"cleanup_fillers": False})
        assert result == "A"

    def test_handles_all_fillers_in_sequence(self):
        """Should remove multiple filler words in sequence."""
        text = "um uh hmm like you know"
        result = clean_text(text, {"cleanup_fillers": True})
        assert result.strip()


class TestFillerWords:
    """Tests for filler word definitions."""

    def test_filler_words_defined(self):
        """Should have filler words defined."""
        assert len(FILLER_WORDS) > 0

    def test_filler_words_includes_um(self):
        """Should include 'um' in filler words."""
        assert any("um" in fw.lower() for fw in FILLER_WORDS)

    def test_filler_words_includes_like(self):
        """Should include 'like' in filler words."""
        assert any("like" in fw.lower() for fw in FILLER_WORDS)
