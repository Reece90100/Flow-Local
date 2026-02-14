import pytest
import json
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from flow_local import load_config, save_config, DEFAULTS, CONFIG_PATH


class TestLoadConfig:
    """Tests for config loading functionality."""

    def test_load_defaults_when_no_config_exists(self, temp_config_dir):
        """Should return defaults when config file doesn't exist."""
        result = load_config()
        assert result == DEFAULTS

    def test_load_merges_defaults_with_existing_config(self, temp_config_dir):
        """Should merge defaults with existing config, keeping custom values."""
        config_data = {"hotkey": "f9", "custom_field": "value"}
        config_path = temp_config_dir / "config.json"
        config_path.write_text(json.dumps(config_data))
        
        result = load_config()
        
        assert result["hotkey"] == "f9"
        assert result["custom_field"] == "value"
        assert result["whisper_model"] == DEFAULTS["whisper_model"]

    def test_load_handles_corrupted_json(self, temp_config_dir):
        """Should return defaults when config file is corrupted."""
        config_path = temp_config_dir / "config.json"
        config_path.write_text("{ invalid json }")
        
        result = load_config()
        
        assert result == DEFAULTS

    def test_load_handles_empty_config_file(self, temp_config_dir):
        """Should return defaults when config file is empty."""
        config_path = temp_config_dir / "config.json"
        config_path.write_text("")
        
        result = load_config()
        
        assert result == DEFAULTS


class TestSaveConfig:
    """Tests for config saving functionality."""

    def test_save_creates_config_file(self, temp_config_dir):
        """Should create config file when saving."""
        config_data = {"hotkey": "ctrl+shift"}
        save_config(config_data)
        
        config_path = temp_config_dir / "config.json"
        assert config_path.exists()

    def test_save_writes_valid_json(self, temp_config_dir):
        """Should write valid JSON to config file."""
        config_data = {"hotkey": "f9", "language": "en"}
        save_config(config_data)
        
        config_path = temp_config_dir / "config.json"
        with open(config_path) as f:
            loaded = json.load(f)
        
        assert loaded == config_data

    def test_save_creates_parent_directories(self, temp_config_dir):
        """Should create parent directories if they don't exist."""
        config_data = {"hotkey": "test"}
        
        save_config(config_data)
        
        assert CONFIG_PATH.parent.exists()

    def test_save_overwrites_existing_config(self, temp_config_dir):
        """Should overwrite existing config file."""
        config_path = temp_config_dir / "config.json"
        
        save_config({"hotkey": "first"})
        save_config({"hotkey": "second"})
        
        with open(config_path) as f:
            loaded = json.load(f)
        
        assert loaded["hotkey"] == "second"
