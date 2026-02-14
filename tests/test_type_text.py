import pytest
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, str(Path(__file__).parent.parent))

from flow_local import type_text


class TestTypeText:
    """Tests for the type_text function."""

    def test_handles_empty_text(self):
        """Should do nothing with empty text."""
        type_text("", "clipboard")
        type_text("", "type")

    @patch('flow_local.pyperclip')
    @patch('flow_local.pyautogui')
    def test_clipboard_method(self, mock_pyautogui, mock_pyperclip):
        """Should use clipboard to insert text."""
        mock_pyperclip.paste.return_value = "original"
        
        type_text("hello world", "clipboard")
        
        mock_pyperclip.copy.assert_called_with("hello world")
        mock_pyautogui.hotkey.assert_called_with("ctrl", "v")

    @patch('flow_local.pyperclip')
    @patch('flow_local.pyautogui')
    def test_clipboard_restores_original(self, mock_pyautogui, mock_pyperclip):
        """Should restore original clipboard after delay."""
        mock_pyperclip.paste.return_value = "original text"
        
        type_text("new text", "clipboard")
        
        time.sleep(0.7)
        
        mock_pyperclip.copy.assert_called_with("original text")

    @patch('flow_local.pyperclip')
    @patch('flow_local.pyautogui')
    def test_type_method(self, mock_pyautogui, mock_pyperclip):
        """Should use typewrite for text insertion."""
        type_text("hello", "type")
        
        mock_pyautogui.typewrite.assert_called_once_with("hello", interval=0.01)

    @patch('flow_local.pyperclip')
    @patch('flow_local.pyautogui')
    def test_clipboard_handles_paste_failure(self, mock_pyautogui, mock_pyperclip):
        """Should handle clipboard paste failure gracefully."""
        mock_pyperclip.paste.side_effect = Exception("Clipboard error")
        
        type_text("test", "clipboard")
        
        mock_pyperclip.copy.assert_called_with("test")

    @patch('flow_local.pyperclip')
    @patch('flow_local.pyautogui')
    def test_clipboard_handles_copy_failure(self, mock_pyautogui, mock_pyperclip):
        """Should handle clipboard copy failure gracefully."""
        mock_pyperclip.copy.side_effect = Exception("Copy error")
        
        type_text("test", "clipboard")

    @patch('flow_local.pyperclip')
    @patch('flow_local.pyautogui')
    def test_invalid_method_defaults_to_typewrite(self, mock_pyautogui, mock_pyperclip):
        """Should default to typewrite for unknown methods."""
        type_text("test", "invalid_method")
        
        mock_pyautogui.typewrite.assert_called_once_with("test", interval=0.01)
