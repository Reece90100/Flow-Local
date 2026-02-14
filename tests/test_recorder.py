import pytest
import sys
import wave
import tempfile
import os
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestRecorder:
    """Tests for the Recorder class."""

    @patch('flow_local.sd')
    def test_recorder_initialization(self, mock_sd):
        """Recorder should initialize with empty frames."""
        from flow_local import Recorder
        rec = Recorder()
        
        assert rec.frames == []
        assert rec.recording is False
        assert rec._stream is None
        assert rec.SR == 16000

    @patch('flow_local.sd')
    @patch('flow_local.np')
    def test_start_recording(self, mock_np, mock_sd):
        """Should start recording when start() is called."""
        from flow_local import Recorder
        
        mock_stream = MagicMock()
        mock_sd.InputStream.return_value = mock_stream
        
        rec = Recorder()
        rec.start()
        
        assert rec.recording is True
        assert rec._stream is not None
        mock_sd.InputStream.assert_called_once()

    @patch('flow_local.sd')
    @patch('flow_local.np')
    @patch('flow_local.tempfile')
    def test_stop_recording(self, mock_tmp, mock_np, mock_sd):
        """Should stop recording and return audio file path."""
        from flow_local import Recorder
        
        mock_stream = MagicMock()
        mock_sd.InputStream.return_value = mock_stream
        mock_np.concatenate.return_value = np.zeros(16000, dtype=np.int16)
        
        mock_tmp_file = MagicMock()
        mock_tmp_file.name = "test_path.wav"
        mock_tmp.NamedTemporaryFile.return_value = mock_tmp_file
        
        rec = Recorder()
        rec.start()
        rec.frames = [np.zeros(16000, dtype=np.int16)]  # Add frames after start
        result = rec.stop()
        
        assert rec.recording is False
        mock_stream.stop.assert_called_once()
        mock_stream.close.assert_called_once()
        assert result == "test_path.wav"

    @patch('flow_local.sd')
    @patch('flow_local.np')
    def test_stop_with_no_frames(self, mock_np, mock_sd):
        """Should return None if no frames were recorded."""
        from flow_local import Recorder
        
        rec = Recorder()
        rec.recording = False
        rec.frames = []
        
        result = rec.stop()
        
        assert result is None

    @patch('flow_local.sd')
    @patch('flow_local.np')
    def test_audio_callback(self, mock_np, mock_sd):
        """Should append audio data when callback is triggered."""
        from flow_local import Recorder
        
        mock_stream = MagicMock()
        mock_sd.InputStream.return_value = mock_stream
        
        mock_indata = np.array([[1, 2, 3]], dtype=np.int16)
        
        rec = Recorder()
        rec.recording = True
        rec._cb(mock_indata, None)
        
        assert len(rec.frames) == 1


class TestTranscriber:
    """Tests for the Transcriber class."""

    def test_transcriber_initialization(self):
        """Should initialize with model name and language."""
        from flow_local import Transcriber
        
        trx = Transcriber("base", "en")
        
        assert trx.model_name == "base"
        assert trx.lang == "en"
        assert trx.m is None

    @patch('flow_local.WhisperModel')
    def test_load_model(self, mock_whisper):
        """Should load Whisper model."""
        from flow_local import Transcriber
        
        mock_model = MagicMock()
        mock_whisper.return_value = mock_model
        
        trx = Transcriber("base", "en")
        trx.load()
        
        mock_whisper.assert_called_once_with("base", device="cpu", compute_type="int8")
        assert trx.m is not None

    @patch('flow_local.WhisperModel')
    def test_transcribe_returns_text(self, mock_whisper):
        """Should return transcribed text."""
        from flow_local import Transcriber
        
        mock_model = MagicMock()
        mock_segment1 = MagicMock()
        mock_segment1.text = "Hello"
        mock_segment2 = MagicMock()
        mock_segment2.text = "world"
        
        mock_model.transcribe.return_value = ([mock_segment1, mock_segment2], None)
        mock_whisper.return_value = mock_model
        
        trx = Transcriber("base", "en")
        trx.m = mock_model
        
        result = trx.transcribe("test.wav")
        
        assert result == "Hello world"

    @patch('flow_local.WhisperModel')
    def test_transcribe_with_auto_language(self, mock_whisper):
        """Should pass None for language when auto."""
        from flow_local import Transcriber
        
        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([], None)
        mock_whisper.return_value = mock_model
        
        trx = Transcriber("base", "auto")
        trx.m = mock_model
        
        trx.transcribe("test.wav")
        
        mock_model.transcribe.assert_called_once()
        call_kwargs = mock_model.transcribe.call_args[1]
        assert call_kwargs.get('language') is None

    @patch('flow_local.WhisperModel')
    def test_transcribe_thread_safety(self, mock_whisper):
        """Should handle concurrent transcriptions."""
        from flow_local import Transcriber
        import threading
        
        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([MagicMock(text="test")], None)
        mock_whisper.return_value = mock_model
        
        trx = Transcriber("base", "en")
        trx.m = mock_model
        
        results = []
        
        def transcribe():
            result = trx.transcribe("test.wav")
            results.append(result)
        
        t1 = threading.Thread(target=transcribe)
        t2 = threading.Thread(target=transcribe)
        
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        
        assert len(results) == 2
