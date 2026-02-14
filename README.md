# 🎙 Flow Local — Offline Voice Dictation

100% offline powered by **OpenAI Whisper** running locally on your machine.

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-49%20passing-brightgreen.svg)]()

## What it does

- **Hold** your hotkey (default: `Windows + Ctrl`) → speak → **release** → text appears wherever your cursor is
- Works in **any app** — email, docs, Slack, code editor, browser, anything
- Removes filler words (um, uh, like…)
- Auto-capitalizes and cleans up punctuation
- Fully **offline** after first-time model download
- Multi-monitor support — follows your mouse
- Transcription history with copy support
- System tray icon (Windows)
- Customizable settings with interactive hotkey capture

---

## Quick Start

### Windows

1. Double-click **`install_windows.bat`**
2. Wait for installation (~2 min)
3. Double-click **`run_flow.bat`**

### macOS / Linux

```bash
bash install_mac_linux.sh
python3 flow_local.py
```

---

## First Run

The **first time** you launch, Flow Local downloads the Whisper AI model:

| Model  | Size  | Speed  | Accuracy |
|--------|-------|--------|----------|
| tiny   | 75 MB | ⚡ Fast | Good     |
| **base** | 145 MB | 🔥 Fast | **Better** (default) |
| small  | 465 MB | OK     | Great    |
| medium | 1.5 GB | Slow   | Excellent |
| large  | 2.9 GB | 🐢 Very Slow | Best |

After download, everything runs **100% offline**.

---

## How to Use

1. Launch the app — you'll see a tray icon (or small control panel)
2. Click somewhere you want to type (email compose box, document, etc.)
3. **Hold** `Windows + Ctrl` and **speak**
4. **Release** — your transcribed text appears!

A small overlay shows status:
- 🔴 Recording… (waveform animation)
- 🟡 Processing… (spinner)
- 🟢 Done! (checkmark)

---

## Features

### Multi-Monitor Support
The app automatically detects which monitor your mouse is on:
- **Window Pill** — Floats at bottom-center of active monitor
- **Waveform Overlay** — Appears on the monitor where you triggered recording

### Interactive Hotkey Configuration
In Settings, click the hotkey box and press your desired key combination — the app captures it automatically!

### Filler Word Removal
Automatically removes common filler words:
- "um", "uh", "umm", "uhh"
- "hmm", "like", "you know"

---

## Settings

Right-click the tray icon → **Settings** or click Settings in the main panel:

- **Hotkey** — Configure via interactive capture (e.g., `windows+ctrl`, `f9`, `ctrl+shift`)
- **Whisper model** — Accuracy vs. speed tradeoff (tiny/base/small/medium/large)
- **Language** — Transcription language (auto-detect or specify)
- **Filler word removal** — Strips "um", "uh", "like" etc.
- **Text insertion method** — clipboard (faster) or type (safer)
- **Show overlay** — Display waveform animation while recording

Settings are saved in `~/.flow_local/config.json`

---

## Development

### Project Structure

```
flow_local/
├── flow_local.py          # Main application (~1,200 lines)
├── requirements.txt       # Python dependencies
├── tests/                 # Test suite (49 tests)
│   ├── test_config.py
│   ├── test_text_utils.py
│   ├── test_recorder.py
│   ├── test_type_text.py
│   └── test_integration.py
├── install_windows.bat   # Windows installer
├── install_mac_linux.sh  # Mac/Linux installer
└── run_flow.bat          # Windows launcher
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=flow_local --cov-report=term-missing

# Run specific test file
pytest tests/test_config.py -v
```

All 49 tests currently passing ✅

### Code Quality

- **Type hints** throughout
- **Thread-safe** operations
- **Exception handling** with specific exception types
- **49 unit & integration tests**

---

## Requirements

- Python 3.8+
- Windows 10/11 (primary)
- macOS/Linux (experimental)
- Microphone
- ~200 MB disk space (for base model)
- No internet needed after first run!

---

## Troubleshooting

### App Won't Start
- Check Python 3.8+ is installed: `python --version`
- Install dependencies: `pip install -r requirements.txt`
- Check for missing DLLs in error messages

### Microphone Not Working
- Ensure microphone is set as default recording device
- Check Windows Privacy settings → Microphone access
- Try a different microphone

### Hotkey Not Responding
- Try a different hotkey combination in settings
- Check if hotkey is used by another application
- Run as Administrator if needed

### Text Not Pasting
- Switch to `type` method in Settings (slower but more compatible)
- Some apps block clipboard paste for security

### Model Too Slow
- Switch to `tiny` model in Settings for faster processing
- Close other CPU-intensive applications

### Hotkey Not Working on Linux
```bash
sudo python3 flow_local.py
# OR add yourself to input group:
sudo usermod -aG input $USER
```

### No Audio on macOS
Grant microphone access: System Preferences → Security & Privacy → Microphone

---

## Privacy

- All audio processing happens **locally on your machine**
- No data is sent anywhere
- Audio files are deleted immediately after transcription
- History is stored only in memory (cleared on restart)
- Config stored locally in `~/.flow_local/`

---

## Contributing

1. Fork the repository
2. Create a dev branch: `git checkout -b dev`
3. Make changes and test: `pytest tests/`
4. Commit: `git commit -m "feat: add feature"`
5. Push to dev: `git push origin dev`
6. Create Pull Request to dev branch

**Note:** We use the `dev` branch for development. Never push directly to `main`.

---

## License

MIT License — see [LICENSE](LICENSE) file

---

## Acknowledgments

- [OpenAI Whisper](https://github.com/openai/whisper) for speech recognition
- Python open-source community

---

**Made with ❤️ for efficient workflows**
