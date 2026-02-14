import pytest
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestAppIntegration:
    """Integration tests for the main App class."""

    @patch('flow_local.sd')
    @patch('flow_local.WhisperModel')
    @patch('flow_local.keyboard')
    @patch('flow_local.pystray')
    @patch('flow_local.pyperclip')
    @patch('flow_local.pyautogui')
    def test_app_initialization(self, mock_ag, mock_pc, mock_tray, mock_kb, mock_ww, mock_sd):
        """App should initialize with default config."""
        from flow_local import App, DEFAULTS
        
        with patch.object(Path, 'exists', return_value=False):
            app = App()
        
        assert app.cfg == DEFAULTS
        assert app._loaded is False
        assert app._held is False
        assert app._combo is False
        assert app._busy is False
        assert app.history == []

    @patch('flow_local.sd')
    @patch('flow_local.WhisperModel')
    @patch('flow_local.keyboard')
    @patch('flow_local.pystray')
    @patch('flow_local.pyperclip')
    @patch('flow_local.pyautogui')
    def test_app_loads_config(self, mock_ag, mock_pc, mock_tray, mock_kb, mock_ww, mock_sd):
        """App should load custom config."""
        from flow_local import App
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"hotkey": "f9", "custom": "value"}, f)
            config_path = f.name
        
        try:
            with patch('flow_local.CONFIG_PATH', Path(config_path)):
                with patch.object(Path, 'exists', return_value=True):
                    app = App()
                    
                    assert app.cfg["hotkey"] == "f9"
                    assert app.cfg["custom"] == "value"
        finally:
            Path(config_path).unlink()

    @patch('flow_local.sd')
    @patch('flow_local.WhisperModel')
    @patch('flow_local.keyboard')
    @patch('flow_local.pystray')
    @patch('flow_local.pyperclip')
    @patch('flow_local.pyautogui')
    def test_hotkey_registration(self, mock_ag, mock_pc, mock_tray, mock_kb, mock_ww, mock_sd):
        """App should register hotkey on load."""
        from flow_local import App
        
        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([MagicMock(text="test")], None)
        mock_ww.return_value = mock_model
        
        with patch.object(Path, 'exists', return_value=False):
            app = App()
            app.trx = mock_model
            app._loaded = True
            app._reg_hotkey()
        
        mock_kb.add_hotkey.assert_called_once()


class TestRecordingPipeline:
    """Integration tests for the recording pipeline."""

    @patch('flow_local.sd')
    @patch('flow_local.np')
    @patch('flow_local.os')
    @patch('flow_local.WhisperModel')
    @patch('flow_local.keyboard')
    @patch('flow_local.pystray')
    @patch('flow_local.pyperclip')
    @patch('flow_local.pyautogui')
    @patch('flow_local.time')
    def test_full_recording_pipeline(self, mock_time, mock_ag, mock_pc, mock_tray, 
                                      mock_kb, mock_ww, mock_os, mock_np, mock_sd):
        """Test complete recording -> transcribe -> type pipeline."""
        import threading
        from flow_local import App, Recorder, Transcriber, clean_text
        
        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([MagicMock(text="Hello world")], None)
        mock_ww.return_value = mock_model
        
        mock_time.sleep = MagicMock()
        
        mock_np.concatenate.return_value = mock_np.array([1,2,3])
        
        mock_stream = MagicMock()
        mock_sd.InputStream.return_value = mock_stream
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            wav_path = f.name
        
        mock_os.unlink = MagicMock()
        
        rec = Recorder()
        rec.frames = [mock_np.array([1,2,3])]
        
        with patch('tempfile.NamedTemporaryFile') as mock_tmp:
            mock_tmp_file = MagicMock()
            mock_tmp_file.name = wav_path
            mock_tmp.return_value = mock_tmp_file
            
            trx = Transcriber("base", "en")
            trx.m = mock_model
            
            result = trx.transcribe(wav_path)
            
            assert result == "Hello world"
        
        if Path(wav_path).exists():
            Path(wav_path).unlink()


class TestSettingsFlow:
    """Tests for settings save/load cycle."""

    def test_settings_roundtrip(self, temp_config_dir):
        """Settings should survive a save/load cycle."""
        from flow_local import load_config, save_config
        
        original_config = {
            "hotkey": "right alt",
            "whisper_model": "small",
            "language": "en",
            "cleanup_fillers": False,
            "typing_method": "type",
            "show_overlay": False,
        }
        
        save_config(original_config)
        loaded = load_config()
        
        assert loaded == original_config

    def test_partial_config_update(self, temp_config_dir):
        """Partial config update should preserve defaults."""
        from flow_local import load_config, save_config, DEFAULTS
        
        save_config({"hotkey": "f9"})
        loaded = load_config()
        
        assert loaded["hotkey"] == "f9"
        assert loaded["whisper_model"] == DEFAULTS["whisper_model"]


class TestConstants:
    """Tests for application constants."""

    def test_default_config_values(self):
        """Should have valid default configuration."""
        from flow_local import DEFAULTS
        
        assert DEFAULTS["hotkey"] is not None
        assert DEFAULTS["whisper_model"] in ["tiny", "base", "small", "medium", "large-v2"]
        assert DEFAULTS["language"] == "en"
        assert isinstance(DEFAULTS["cleanup_fillers"], bool)
        assert DEFAULTS["typing_method"] in ["clipboard", "type"]
        assert isinstance(DEFAULTS["show_overlay"], bool)

    def test_whisper_models_list(self):
        """Should have valid Whisper model list."""
        from flow_local import WHISPER_MODELS
        
        assert "base" in WHISPER_MODELS
        assert len(WHISPER_MODELS) >= 3
