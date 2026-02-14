import pytest
import tempfile
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

@pytest.fixture
def temp_config_dir(monkeypatch):
    """Create a temporary config directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / ".flow_local"
        config_path.mkdir()
        monkeypatch.setattr("flow_local.CONFIG_PATH", config_path / "config.json")
        yield config_path


@pytest.fixture
def mock_config():
    """Default configuration values."""
    return {
        "hotkey": "windows+ctrl",
        "whisper_model": "base",
        "language": "en",
        "cleanup_fillers": True,
        "typing_method": "clipboard",
        "show_overlay": True,
    }


@pytest.fixture
def mock_deps():
    """Mock all external dependencies."""
    with patch.dict(sys.modules, {
        'numpy': MagicMock(),
        'sounddevice': MagicMock(),
        'faster_whisper': MagicMock(),
        'keyboard': MagicMock(),
        'pyperclip': MagicMock(),
        'pyautogui': MagicMock(),
        'PIL': MagicMock(),
        'pystray': MagicMock(),
    }):
        yield


@pytest.fixture
def sample_audio_file():
    """Create a temporary WAV file for testing."""
    import wave
    import numpy as np
    
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name
    
    sample_rate = 16000
    duration = 1
    frequency = 440
    
    t = np.linspace(0, duration, int(sample_rate * duration))
    audio_data = (np.sin(2 * np.pi * frequency * t) * 32767).astype(np.int16)
    
    with wave.open(tmp_path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_data.tobytes())
    
    yield tmp_path
    
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)
