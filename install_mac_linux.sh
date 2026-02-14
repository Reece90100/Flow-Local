#!/bin/bash
set -e

echo ""
echo " ============================================"
echo "   FLOW LOCAL - Offline Voice Dictation"
echo "   Installer for macOS / Linux"
echo " ============================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 not found!"
    echo "  macOS: brew install python3"
    echo "  Ubuntu/Debian: sudo apt install python3 python3-pip"
    exit 1
fi

PYTHON=$(command -v python3)
echo "[1/5] Python found: $($PYTHON --version)"

# Check pip
if ! $PYTHON -m pip --version &>/dev/null; then
    echo "Installing pip..."
    curl -sS https://bootstrap.pypa.io/get-pip.py | $PYTHON
fi
echo "[2/5] pip ready."

# macOS: install portaudio for sounddevice
if [[ "$OSTYPE" == "darwin"* ]]; then
    if ! command -v brew &>/dev/null; then
        echo ""
        echo "  [!] Homebrew not found. Installing..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    echo "[3/5] Installing portaudio (macOS requirement)..."
    brew install portaudio 2>/dev/null || true
else
    echo "[3/5] Installing system audio libraries..."
    if command -v apt-get &>/dev/null; then
        sudo apt-get install -y portaudio19-dev python3-pyaudio libportaudio2 xdotool 2>/dev/null || true
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y portaudio-devel 2>/dev/null || true
    fi
fi

echo "[4/5] Installing Python packages..."
$PYTHON -m pip install \
    faster-whisper \
    sounddevice \
    numpy \
    pyperclip \
    pyautogui \
    keyboard \
    Pillow \
    pystray \
    --quiet

echo "[5/5] Creating launcher..."
cat > run_flow.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
python3 flow_local.py
EOF
chmod +x run_flow.sh

# macOS: create .app-like launcher
if [[ "$OSTYPE" == "darwin"* ]]; then
    cat > "Flow Local.command" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
python3 flow_local.py
EOF
    chmod +x "Flow Local.command"
    echo "  macOS launcher created: 'Flow Local.command' (double-click to run)"
fi

echo ""
echo " ============================================"
echo "   Installation complete!"
echo ""
echo "   To run:"
if [[ "$OSTYPE" == "darwin"* ]]; then
echo "     Double-click 'Flow Local.command'"
echo "     OR: bash run_flow.sh"
else
echo "     bash run_flow.sh"
echo "     OR: python3 flow_local.py"
fi
echo ""
echo "   FIRST RUN: Whisper will download the AI model"
echo "   (~75MB for 'base' model). After that, fully offline!"
echo " ============================================"
echo ""

# On Linux, note keyboard permissions
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo " NOTE for Linux: The 'keyboard' package may need root."
    echo " If hotkeys don't work, run with: sudo python3 flow_local.py"
    echo " OR add your user to the 'input' group:"
    echo "   sudo usermod -aG input \$USER  (then log out and back in)"
    echo ""
fi
