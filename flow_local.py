#!/usr/bin/env python3
"""
Flow Local - Offline Voice Dictation
Hold the hotkey to record, release to transcribe and type anywhere.
"""

import sys, os, time, threading, wave, tempfile, queue, json, math, random, platform, re
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from typing import Dict, Any, Optional
import ctypes

# ── Dependency check ──────────────────────────────────────────────────────────
MISSING = []
try:    import numpy as np
except ImportError: MISSING.append("numpy")
try:    import sounddevice as sd
except ImportError: MISSING.append("sounddevice")
try:    from faster_whisper import WhisperModel
except ImportError: MISSING.append("faster-whisper")
try:    import keyboard
except ImportError: MISSING.append("keyboard")
try:    import pyperclip
except ImportError: MISSING.append("pyperclip")
try:
    import pyautogui
    pyautogui.FAILSAFE = False
    pyautogui.PAUSE    = 0.01
except ImportError: MISSING.append("pyautogui")

try:    from PIL import Image, ImageDraw;  PIL_AVAILABLE  = True
except ImportError: PIL_AVAILABLE  = False
try:    import pystray;                    TRAY_AVAILABLE = True
except ImportError: TRAY_AVAILABLE = False

IS_WIN = platform.system() == "Windows"

# ── Config ────────────────────────────────────────────────────────────────────
CONFIG_PATH = Path.home() / ".flow_local" / "config.json"
DEFAULTS = {
    "hotkey":          "windows+ctrl",
    "whisper_model":   "base",
    "language":        "en",
    "cleanup_fillers": True,
    "typing_method":   "clipboard",
    "show_overlay":    True,
}
FILLER_WORDS = ["um,","uh,","umm,","uhh,","hmm,"," um "," uh "," umm "," uhh "," hmm "," like, ","you know,"]
WHISPER_MODELS = ["tiny","base","small","medium","large-v2"]

def load_config() -> Dict[str, Any]:
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH) as f:
                return {**DEFAULTS, **json.load(f)}
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to load config: {e}")
        except Exception as e:
            print(f"Warning: Unexpected error loading config: {e}")
    return dict(DEFAULTS)

def save_config(cfg: Dict[str, Any]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH,"w") as f: json.dump(cfg, f, indent=2)

def clean_text(text: str, cfg: Dict[str, Any]) -> str:
    if cfg.get("cleanup_fillers"):
        for fw in FILLER_WORDS: text = text.replace(fw," ")
    text = re.sub(r"  +"," ",text).strip()
    return text[0].upper()+text[1:] if text else text

def type_text(text: str, method: str) -> None:
    if not text: return
    if method == "clipboard":
        orig = ""
        try:
            orig = pyperclip.paste()
        except Exception as e:
            print(f"Warning: Could not read clipboard: {e}")
        try:
            pyperclip.copy(text)
        except Exception as e:
            print(f"Warning: Could not copy to clipboard: {e}")
            return
        time.sleep(0.08)
        pyautogui.hotkey("ctrl","v")
        def _restore():
            time.sleep(0.3)
            try:
                if orig:
                    pyperclip.copy(orig)
            except Exception as e:
                print(f"Warning: Could not restore clipboard: {e}")
        threading.Thread(target=_restore, daemon=True).start()
    else:
        pyautogui.typewrite(text, interval=0.01)

# ── Thread-safe UI queue ──────────────────────────────────────────────────────
_uiq = queue.Queue()
def ui(fn, *a, **kw): _uiq.put((fn, a, kw))

# ── Helpers ───────────────────────────────────────────────────────────────────
BG      = "#0d0d0d"
BG1     = "#111111"
BG2     = "#1a1a1a"
BG3     = "#222222"
RED     = "#ff3b5c"
RED2    = "#ff1f45"
GREEN   = "#1db954"
MUTED   = "#444444"
MUTED2  = "#555555"
WHITE   = "#ffffff"
OFFWHITE= "#cccccc"

def style_window(win, w, h, centered=True, border=True, alpha=0.97):
    win.configure(bg=BG)
    win.resizable(False, False)
    win.attributes("-topmost", True)
    win.attributes("-alpha", alpha)
    win.update_idletasks()
    sw = win.winfo_screenwidth(); sh = win.winfo_screenheight()
    if centered:
        win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
    if border:
        # 1px border via outer frame trick
        win.configure(bg=BG3)
        f = tk.Frame(win, bg=BG); f.place(x=1,y=1,width=w-2,height=h-2)
        return f
    return win

def pill_button(parent, text, cmd, accent=False, full_width=False):
    bg  = RED  if accent else BG2
    hbg = RED2 if accent else BG3
    fg  = WHITE
    b = tk.Label(parent, text=text,
                 font=("Segoe UI", 10, "bold"),
                 bg=bg, fg=fg, pady=11, cursor="hand2", anchor="center")
    if full_width: b.pack(fill="x", pady=(0,6))
    b.bind("<Button-1>", lambda e: cmd())
    b.bind("<Enter>",    lambda e: b.configure(bg=hbg))
    b.bind("<Leave>",    lambda e: b.configure(bg=bg))
    return b

# ── Recording overlay (pill with waveform) ────────────────────────────────────
class RecordingOverlay:
    W, H       = 160, 32
    BAR_COUNT  = 18
    BAR_W      = 2
    BAR_GAP    = 1
    BAR_MAX_H  = 14
    BAR_MIN_H  = 2

    def __init__(self, root):
        self.root    = root
        self.win     = None
        self.canvas  = None
        self._state  = "idle"
        self._after_id    = None
        self._tick      = 0.0
        self._wave_phases = [random.uniform(0, 2*math.pi) for _ in range(self.BAR_COUNT)]
        self._wave_speeds = [random.uniform(0.08, 0.18)   for _ in range(self.BAR_COUNT)]
        self._pill   = None   # reference to WindowPill for monitor coords

    def set_pill(self, pill):
        self._pill = pill

    def _get_monitor_pos(self):
        """Return (x, y) to place waveform pill — same monitor as the window pill."""
        if self._pill and hasattr(self._pill, "_mon_left") and self._pill._mon_left is not None:
            mx  = self._pill._mon_left
            mw  = self._pill._mon_w
            mb  = self._pill._mon_bottom
            x   = mx + (mw - self.W) // 2
            y   = mb - self.H - 20
            return x, y
        # Fallback: primary screen
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        return (sw - self.W) // 2, sh - self.H - 20

    def _build(self):
        if self.win and self.win.winfo_exists(): return
        self.win = tk.Toplevel(self.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", 0.0)
        _tc = "#010101"
        self.win.configure(bg=_tc)
        if IS_WIN:
            self.win.wm_attributes("-transparentcolor", _tc)
        x, y = self._get_monitor_pos()
        self.win.geometry(f"{self.W}x{self.H}+{x}+{y}")
        self.canvas = tk.Canvas(self.win, width=self.W, height=self.H,
                                bg=_tc, highlightthickness=0, bd=0)
        self.canvas.place(x=0,y=0)
        self._draw_base()
        self.win.withdraw()

    def _draw_base(self):
        w,h = self.W, self.H; r = h//2; c = self.canvas; c.delete("base")
        pill_bg = "#1c1c1e"
        c.create_arc(0,0,r*2,h,   start=90, extent=180, fill=pill_bg, outline="", tags="base")
        c.create_arc(w-r*2,0,w,h, start=270,extent=180, fill=pill_bg, outline="", tags="base")
        c.create_rectangle(r,0,w-r,h, fill=pill_bg, outline=pill_bg, tags="base")

    def _draw_wave(self, accent):
        c = self.canvas; c.delete("wave")
        n = self.BAR_COUNT
        total = n*self.BAR_W + (n-1)*self.BAR_GAP
        sx = (self.W - total)//2; cy = self.H//2
        for i in range(n):
            t = self._tick
            amp = (math.sin(t*self._wave_speeds[i]*6+self._wave_phases[i])*0.5 +
                   math.sin(t*self._wave_speeds[i]*3.7+self._wave_phases[i]*1.3)*0.3 + 0.2)
            amp = max(0.04, min(1.0,(amp+0.15)/1.15))
            bh  = int(self.BAR_MIN_H + amp*(self.BAR_MAX_H-self.BAR_MIN_H))
            x0  = sx + i*(self.BAR_W+self.BAR_GAP)
            dist = abs(i-n//2)/(n//2)
            al   = int(255*(0.55+0.45*(1-dist)))
            hx   = accent.lstrip("#")
            r,g,b = int(hx[0:2],16), int(hx[2:4],16), int(hx[4:6],16)
            col  = f"#{int(r*al/255):02x}{int(g*al/255):02x}{int(b*al/255):02x}"
            c.create_rectangle(x0, cy-bh//2, x0+self.BAR_W, cy+bh//2,
                                fill=col, outline="", tags="wave")

    def _draw_spinner(self, accent):
        c = self.canvas; c.delete("wave")
        cx,cy = self.W//2, self.H//2; ang0 = self._tick*4.5
        for i in range(8):
            a  = ang0 + (2*math.pi/8)*i
            dx = cx + 8*math.cos(a); dy = cy + 8*math.sin(a)
            fade = int(80+170*(i/8))
            hx = accent.lstrip("#")
            r,g,b = int(hx[0:2],16),int(hx[2:4],16),int(hx[4:6],16)
            col = f"#{int(r*fade/255):02x}{int(g*fade/255):02x}{int(b*fade/255):02x}"
            c.create_oval(dx-2,dy-2,dx+2,dy+2, fill=col, outline="", tags="wave")

    def _draw_icon(self, sym, col):
        self.canvas.delete("wave")
        self.canvas.create_text(self.W//2, self.H//2, text=sym,
                                font=("Segoe UI",13,"bold"), fill=col, tags="wave")

    def show(self, state):
        self._build()
        self._state = state; self._tick = 0.0
        if self._after_id: self.root.after_cancel(self._after_id); self._after_id = None
        # Reposition to active monitor every time we show
        x, y = self._get_monitor_pos()
        self.win.geometry(f"{self.W}x{self.H}+{x}+{y}")
        self._draw_base()
        self.win.deiconify(); self.win.lift()
        self._fade(0.95, 8, 18)
        if state in ("recording","processing"): self._anim()
        elif state == "done":  self._draw_icon("✓", GREEN)
        elif state == "error": self._draw_icon("✗", "#ff4444")

    def hide(self, ms=1200): self.root.after(ms, self._fade_out)

    def _fade_out(self):
        if self._after_id: self.root.after_cancel(self._after_id); self._after_id = None
        self._fade(0.0, 12, 25, on_done=self._do_hide)

    def _do_hide(self):
        if self.win and self.win.winfo_exists(): self.win.withdraw()

    def _fade(self, target, steps, ms, step=0, on_done=None):
        if not (self.win and self.win.winfo_exists()): return
        try:
            cur = self.win.attributes("-alpha")
        except Exception:
            return
        na = cur + (target-cur)*(step+1)/steps
        try:
            self.win.attributes("-alpha", max(0.0,min(1.0,na)))
        except Exception:
            return
        if step < steps-1: self.root.after(ms, self._fade, target, steps, ms, step+1, on_done)
        elif on_done: on_done()

    def _anim(self):
        if not (self.win and self.win.winfo_exists()): return
        if self._state not in ("recording","processing"): return
        self._tick += 1; self._draw_base()
        if self._state == "recording":
            self._draw_wave(RED)
            self.canvas.delete("mic")
            self.canvas.create_oval(7, self.H//2-3, 14, self.H//2+3,
                                    fill=RED, outline="", tags="mic")
        else:
            self._draw_spinner("#f0a500")
        self._after_id = self.root.after(40, self._anim)


# ── Active-window pill indicator ──────────────────────────────────────────────
class WindowPill:
    """
    Wispr Flow-style pill:
    - Floats at bottom-centre of whichever MONITOR the mouse is on
    - Collapsed: thin capsule bar (like iPhone home indicator)
    - Hovered:   expands to show hotkey hint text
    - Hides while recording (waveform overlay takes over)
    """
    # Collapsed = thin bar, Expanded = full hint pill
    CW, CH = 48, 5      # collapsed: tiny bar
    EW, EH = 340, 36    # expanded: hint pill

    BOTTOM_MARGIN = 20  # px above taskbar

    def __init__(self, root, hotkey_str="Windows + Ctrl"):
        self.root        = root
        self.hotkey_str  = hotkey_str
        self.win         = None
        self.canvas      = None
        self._poll       = None
        self._suppressed = False
        self._expanded   = False
        self._anim_id    = None
        self._cur_w      = self.CW
        self._cur_h      = self.CH
        self._last_pos   = None
        self._mon_left   = None
        self._mon_w      = None
        self._mon_bottom = None

        class RECT(ctypes.Structure):
            _fields_ = [("left",  ctypes.c_long), ("top",   ctypes.c_long),
                        ("right", ctypes.c_long), ("bottom",ctypes.c_long)]
        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize",    ctypes.c_ulong),
                        ("rcMonitor", RECT), ("rcWork", RECT),
                        ("dwFlags",   ctypes.c_ulong)]
        self._RECT        = RECT
        self._POINT       = POINT
        self._MONITORINFO = MONITORINFO

    def start(self):
        self._build()
        # Initialize monitor position immediately
        try:
            self._update_monitor_position()
        except Exception:
            pass
        self._tick()

    def suppress(self):
        # Refresh monitor position NOW so overlay spawns on correct monitor
        try:
            self._update_monitor_position()
        except Exception:
            pass
        self._suppressed = True
        if self.win and self.win.winfo_exists():
            self.win.withdraw()

    def unsuppress(self):
        self._suppressed = False

    # ── Build ──────────────────────────────────────────────────────────────

    def _build(self):
        self.win = tk.Toplevel(self.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", 0.0)
        # Use magic transparent colour so rounded corners clip cleanly
        self._tickc = "#010101"
        self.win.configure(bg=self._tickc)
        if IS_WIN:
            self.win.wm_attributes("-transparentcolor", self._tickc)

        self.canvas = tk.Canvas(self.win, bg=self._tickc, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.win.geometry(f"{self.CW}x{self.CH}+0+0")
        self._draw(self.CW, self.CH, False)
        self.win.withdraw()

        # Hover bindings
        self.win.bind("<Enter>",  lambda e: self._on_enter())
        self.win.bind("<Leave>",  lambda e: self._on_leave())
        self.win.bind("<Button-1>", lambda e: self._on_click())
        self.canvas.bind("<Enter>",  lambda e: self._on_enter())
        self.canvas.bind("<Leave>",  lambda e: self._on_leave())
        self.canvas.bind("<Button-1>", lambda e: self._on_click())

    def _draw(self, w, h, expanded):
        c = self.canvas
        c.configure(width=w, height=h)
        c.delete("all")
        r = h // 2

        tc = "#010101"   # transparent colour
        bg = "#1c1c1e"
        c.configure(bg=tc)
        if expanded:
            # Pill background
            c.create_arc(0,      0, r*2,   h, start=90,  extent=180, fill=bg, outline="")
            c.create_arc(w-r*2,  0, w,     h, start=270, extent=180, fill=bg, outline="")
            c.create_rectangle(r, 0, w-r,  h, fill=bg, outline="")

            # Draw text in 3 segments using font.measure() for exact placement
            from tkinter import font as tkfont
            fn_normal = tkfont.Font(family="Segoe UI", size=10)
            fn_bold   = tkfont.Font(family="Segoe UI", size=10, weight="bold")

            pre  = "Click or hold "
            hk   = self.hotkey_str
            post = " to start dictating"

            w_pre  = fn_normal.measure(pre)
            w_hk   = fn_bold.measure(hk)
            w_post = fn_normal.measure(post)
            total  = w_pre + w_hk + w_post

            cx = w // 2
            cy = h // 2 + 1
            x  = cx - total // 2   # left edge of first segment

            c.create_text(x,          cy, text=pre,  font=fn_normal,
                          fill="#888888", anchor="nw", tags="hint")
            c.create_text(x + w_pre,  cy, text=hk,   font=fn_bold,
                          fill="#d05cce", anchor="nw", tags="hint")
            c.create_text(x + w_pre + w_hk, cy, text=post, font=fn_normal,
                          fill="#888888", anchor="nw", tags="hint")
        else:
            # Collapsed: rounded bar (like iPhone home indicator)
            bar_bg = "#3a3a3c"
            c.configure(bg=tc)
            c.create_arc(0,    0, r*2, h, start=90,  extent=180, fill=bar_bg, outline="")
            c.create_arc(w-r*2,0, w,   h, start=270, extent=180, fill=bar_bg, outline="")
            c.create_rectangle(r, 0, w-r, h, fill=bar_bg, outline="")

    # ── Hover expand/collapse ──────────────────────────────────────────────

    def _on_enter(self):
        if self._suppressed or self._expanded: return
        self._expanded = True
        self._start_w = self._cur_w; self._start_h = self._cur_h
        self._animate_to(self.EW, self.EH)

    def _on_leave(self):
        if not self._expanded: return
        self._expanded = False
        self._start_w = self._cur_w; self._start_h = self._cur_h
        self._animate_to(self.CW, self.CH)

    def _on_click(self):
        # Clicking pill triggers record — same as hotkey down
        pass  # App will bind this via set_click_callback

    def _animate_to(self, target_w, target_h, steps=8, step=0):
        if self._anim_id:
            self.root.after_cancel(self._anim_id)
        if not (self.win and self.win.winfo_exists()): return

        t   = (step + 1) / steps
        # Ease out cubic
        t2  = 1 - (1 - t) ** 3
        w   = int(self._start_w + (target_w - self._start_w) * t2)
        h   = int(self._start_h + (target_h - self._start_h) * t2)
        w   = max(self.CW, w); h = max(self.CH, h)

        expanded = (target_w == self.EW)
        self._draw(w, h, expanded and step >= steps - 2)
        self._reposition_at_current(w, h)

        if step < steps - 1:
            self._anim_id = self.root.after(16, self._animate_to,
                                             target_w, target_h, steps, step + 1)
        else:
            self._cur_w = target_w; self._cur_h = target_h

    def _start_anim(self, target_w, target_h):
        self._start_w = self._cur_w
        self._start_h = self._cur_h
        self._animate_to(target_w, target_h)

    # ── Position tracking ──────────────────────────────────────────────────

    def _tick(self):
        if not self._suppressed:
            try:
                self._update_monitor_position()
            except Exception:
                pass
        self._poll = self.root.after(80, self._tick)

    def _get_mouse_monitor_rect(self):
        """Return (mx, my, mw, mh) of the monitor the mouse is currently on."""
        if not IS_WIN:
            return (0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())

        pt = self._POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))

        MONITOR_DEFAULTTONEAREST = 0x00000002
        hmon = ctypes.windll.user32.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)
        if not hmon:
            return (0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())

        mi = self._MONITORINFO()
        mi.cbSize = ctypes.sizeof(self._MONITORINFO)
        ctypes.windll.user32.GetMonitorInfoW(hmon, ctypes.byref(mi))
        r = mi.rcWork   # use work area (excludes taskbar)
        return (r.left, r.top, r.right - r.left, r.bottom - r.top)

    def _update_monitor_position(self):
        mx, my, mw, mh = self._get_mouse_monitor_rect()
        # Store monitor info for use during animation
        self._mon_left   = mx
        self._mon_w      = mw
        self._mon_bottom = my + mh
        w = self._cur_w; h = self._cur_h
        self._reposition_at_current(w, h, base_x=mx, base_mw=mw,
                                    base_y=my + mh)
        fa = 0.90 if self._expanded else 0.75
        try:
            self.win.attributes("-alpha", fa)
        except Exception as e:
            print(f"Warning: Could not set window alpha: {e}")

    def _reposition_at_current(self, w, h, base_x=None, base_mw=None, base_y=None):
        """Move pill to bottom-centre of current monitor."""
        if not (self.win and self.win.winfo_exists()): return

        if base_x is not None:
            px = base_x + (base_mw - w) // 2
            py = base_y - h - self.BOTTOM_MARGIN
            if (px, py, w, h) != self._last_pos:
                self.win.geometry(f"{w}x{h}+{px}+{py}")
                self._last_pos = (px, py, w, h)
            if not self.win.winfo_viewable():
                self.win.deiconify()
            self.win.lift()
        else:
            # During animation: re-centre around last known monitor centre
            if self._last_pos:
                px, py, ow, oh = self._last_pos
                # last_pos stores top-left of the collapsed pill
                # Recover monitor centre-x = px + ow//2 + (EW-CW)//2 if expanding
                # Simpler: just use last monitor info stored
                mx = self._mon_left if hasattr(self,'_mon_left') else px
                mw = self._mon_w    if hasattr(self,'_mon_w')    else self.EW
                my_bottom = self._mon_bottom if hasattr(self,'_mon_bottom') else py + oh + self.BOTTOM_MARGIN
                npx = mx + (mw - w) // 2
                npy = my_bottom - h - self.BOTTOM_MARGIN
                self.win.geometry(f"{w}x{h}+{npx}+{npy}")

    def set_hotkey_str(self, s):
        self.hotkey_str = s

    def stop(self):
        if self._poll: self.root.after_cancel(self._poll)
        if self.win and self.win.winfo_exists(): self.win.destroy()


# ── Audio recorder ────────────────────────────────────────────────────────────
class Recorder:
    SR: int = 16000
    def __init__(self) -> None:
        self.frames: list = []
        self.recording: bool = False
        self._stream = None

    def start(self) -> None:
        self.frames = []
        self.recording = True
        self._stream = sd.InputStream(samplerate=self.SR, channels=1, dtype="int16",
                                  callback=self._cb)
        self._stream.start()

    def _cb(self, indata, *_) -> None:
        if self.recording:
            self.frames.append(indata.copy())

    def stop(self) -> Optional[str]:
        self.recording = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        if not self.frames:
            return None
        data = np.concatenate(self.frames, axis=0)
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        with wave.open(tmp.name, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.SR)
            wf.writeframes(data.tobytes())
        return tmp.name


# ── Transcriber ───────────────────────────────────────────────────────────────
class Transcriber:
    def __init__(self, model: str, lang: str) -> None:
        self.model_name: str = model
        self.lang: str = lang
        self.m = None
        self._lk = threading.Lock()

    def load(self, cb: Optional[callable] = None) -> None:
        if cb:
            cb(f"Loading whisper/{self.model_name}…")
        self.m = WhisperModel(self.model_name, device="cpu", compute_type="int8")
        if cb:
            cb("Ready ✓")

    def transcribe(self, path: str) -> str:
        with self._lk:
            lang = self.lang if self.lang != "auto" else None
            segs, _ = self.m.transcribe(path, language=lang, beam_size=5, vad_filter=True)
            return " ".join(s.text for s in segs).strip()


# ── Main application ──────────────────────────────────────────────────────────
class App:
    def __init__(self) -> None:
        self.cfg: Dict[str, Any] = load_config()
        self.rec: Recorder = Recorder()
        self.trx = None
        self._loaded: bool = False
        self._held: bool = False
        self._combo: bool = False
        self._busy: bool = False
        self._state_lock: threading.Lock = threading.Lock()
        self.history: list = []
        self._history_lock: threading.Lock = threading.Lock()

        self.root: tk.Tk = tk.Tk()
        self.root.withdraw()
        self.root.title("Flow Local")
        if IS_WIN:
            self.root.wm_attributes("-toolwindow", True)

        self.overlay: RecordingOverlay = RecordingOverlay(self.root)
        hk_disp = load_config().get("hotkey","windows+ctrl").replace("+"," + ").title()
        self.pill: WindowPill = WindowPill(self.root, hotkey_str=hk_disp)
        self.overlay.set_pill(self.pill)

        self._splash_status: tk.StringVar = tk.StringVar(value="Initializing…")
        self._splash = None
        self._panel = None
        self._tickray = None

    def _is_busy(self) -> bool:
        with self._state_lock:
            return self._busy

    def _set_busy(self, value: bool) -> None:
        with self._state_lock:
            self._busy = value

    def _is_held(self) -> bool:
        with self._state_lock:
            return self._held

    def _set_held(self, value: bool) -> None:
        with self._state_lock:
            self._held = value

    def _is_combo(self) -> bool:
        with self._state_lock:
            return self._combo

    def _set_combo(self, value: bool) -> None:
        with self._state_lock:
            self._combo = value

    def _add_history(self, text: str) -> None:
        with self._history_lock:
            self.history.append(text)

    # ── Run ───────────────────────────────────────────────────────────────────
    def run(self) -> None:
        if MISSING:
            self._show_missing(); return
        self._build_splash()
        threading.Thread(target=self._load_bg, daemon=True).start()
        self._poll()
        self.root.mainloop()

    def _poll(self) -> None:
        try:
            while True:
                fn, a, kw = _uiq.get_nowait()
                fn(*a, **kw)
        except queue.Empty:
            pass
        self.root.after(30, self._poll)

    # ── Model load ────────────────────────────────────────────────────────────
    def _load_bg(self) -> None:
        try:
            self.trx = Transcriber(self.cfg["whisper_model"], self.cfg["language"])
            self.trx.load(cb=lambda m: ui(self._splash_status.set, m))
            self._loaded = True
            self._reg_hotkey()
            ui(self._on_ready)
        except Exception as e:
            ui(self._on_error, str(e))

    def _on_ready(self):
        self._close_splash()
        self._setup_tray()
        self._show_panel()
        self.pill.start()

    def _on_error(self, msg):
        self._close_splash()
        messagebox.showerror("Flow Local", msg)
        self.root.quit()

    # ── Hotkeys ───────────────────────────────────────────────────────────────
    def _reg_hotkey(self):
        hk = self.cfg.get("hotkey","windows+ctrl")
        try:
            keyboard.unhook_all()
            if "+" in hk:
                self._set_combo(False)
                keyboard.add_hotkey(hk, self._combo_dn, suppress=False)
                for k in [p.strip() for p in hk.split("+")]:
                    keyboard.on_release_key(k, self._combo_up, suppress=False)
            else:
                keyboard.on_press_key(hk,   self._key_dn, suppress=False)
                keyboard.on_release_key(hk, self._key_up, suppress=False)
        except Exception as e:
            ui(messagebox.showerror, "Hotkey Error", str(e))

    def _unreg(self):
        try:
            keyboard.unhook_all()
        except Exception as e:
            print(f"Warning: Could not unregister hotkey: {e}")

    def _key_dn(self, e):
        if not self._is_held() and not self._is_busy():
            self._set_held(True); ui(self._start_rec)
    def _key_up(self, e):
        if self._is_held():
            self._set_held(False)
            threading.Thread(target=self._stop_trx, daemon=True).start()
    def _combo_dn(self):
        if not self._is_combo() and not self._is_busy():
            self._set_combo(True); self._set_held(True); ui(self._start_rec)
    def _combo_up(self, e):
        if self._is_combo():
            self._set_combo(False); self._set_held(False)
            threading.Thread(target=self._stop_trx, daemon=True).start()

    # ── Record / transcribe ───────────────────────────────────────────────────
    def _start_rec(self):
        self.pill.suppress()   # hide window pill — waveform overlay takes over
        if self.cfg.get("show_overlay"): self.overlay.show("recording")
        threading.Thread(target=self.rec.start, daemon=True).start()

    def _stop_trx(self):
        self._set_busy(True)
        try:
            wav = self.rec.stop()
            if not wav:
                ui(self.overlay.show,"error"); ui(self.overlay.hide,1500)
                self.root.after(1600, self.pill.unsuppress); return
            ui(self.overlay.show,"processing")
            text = self.trx.transcribe(wav); os.unlink(wav)
            if text:
                text = clean_text(text, self.cfg)
                self._add_history(text)
                ui(self.overlay.show,"done"); ui(self.overlay.hide,1200)
                time.sleep(0.2)
                type_text(text, self.cfg.get("typing_method","clipboard"))
            else:
                ui(self.overlay.show,"error"); ui(self.overlay.hide,1500)
        except Exception as e:
            print(f"Error during transcription: {e}")
            ui(self.overlay.show,"error"); ui(self.overlay.hide,2000)
        finally:
            self._set_busy(False)
            # Bring pill back after overlay has finished fading out
            ui(self.root.after, 1400, self.pill.unsuppress)

    # ── Splash ────────────────────────────────────────────────────────────────
    def _build_splash(self):
        s = tk.Toplevel(self.root)
        s.overrideredirect(True)
        s.configure(bg=BG3)
        s.attributes("-topmost", True)

        w, h = 380, 240
        s.update_idletasks()
        sw = s.winfo_screenwidth(); sh = s.winfo_screenheight()
        s.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

        inner = tk.Frame(s, bg=BG)
        inner.place(x=1, y=1, width=w-2, height=h-2)

        # Mic circle
        cv = tk.Canvas(inner, width=60, height=60, bg=BG, highlightthickness=0)
        cv.pack(pady=(28,0))
        cv.create_oval(3,3,57,57, fill=BG1, outline=RED, width=2)
        cv.create_text(30,31, text="🎙", font=("Segoe UI",22))

        tk.Label(inner, text="Flow Local",
                 font=("Segoe UI",18,"bold"), bg=BG, fg=WHITE).pack(pady=(8,2))
        tk.Label(inner, text="Offline Voice Dictation",
                 font=("Segoe UI",9), bg=BG, fg=MUTED).pack()

        self._pb = ttk.Progressbar(inner, mode="indeterminate", length=270)
        self._pb.pack(pady=14); self._pb.start(10)

        tk.Label(inner, textvariable=self._splash_status,
                 font=("Segoe UI",9), bg=BG, fg=RED).pack()

        s.protocol("WM_DELETE_WINDOW", self._quit)
        self._splash = s

    def _close_splash(self):
        if self._splash and self._splash.winfo_exists():
            self._pb.stop(); self._splash.destroy(); self._splash = None

    # ── Tray ──────────────────────────────────────────────────────────────────
    def _setup_tray(self):
        if not (TRAY_AVAILABLE and PIL_AVAILABLE): return
        img  = self._tray_icon()
        hk   = self.cfg.get("hotkey","windows+ctrl").replace("+"," + ").title()
        menu = pystray.Menu(
            pystray.MenuItem("Flow Local  ✓", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(f"Hotkey: {hk}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Show window",  lambda *_: ui(self._show_panel)),
            pystray.MenuItem("Settings",     lambda *_: ui(self._show_settings)),
            pystray.MenuItem("History",      lambda *_: ui(self._show_history)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit",         lambda *_: ui(self._quit)),
        )
        self._tickray = pystray.Icon("flow_local", img, "Flow Local", menu)
        threading.Thread(target=self._tickray.run, daemon=True).start()

    def _tray_icon(self, size=64):
        img = Image.new("RGBA",(size,size),(0,0,0,0))
        d   = ImageDraw.Draw(img)
        d.ellipse([2,2,size-2,size-2], fill="#ff3b5c")
        cx = size//2
        d.rounded_rectangle([cx-8,10,cx+8,36], radius=8, fill="white")
        d.arc([cx-14,28,cx+14,50], 0,180, fill="white", width=3)
        d.line([cx,50,cx,56], fill="white", width=3)
        d.line([cx-8,56,cx+8,56], fill="white", width=3)
        return img

    # ── Main panel ────────────────────────────────────────────────────────────
    def _show_panel(self):
        # If already open, bring to front
        if self._panel and self._panel.winfo_exists():
            self._panel.deiconify(); self._panel.lift(); return

        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.97)
        win.configure(bg=BG3)

        W, H = 400, 540
        win.update_idletasks()
        sw = win.winfo_screenwidth(); sh = win.winfo_screenheight()
        win.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")

        inner = tk.Frame(win, bg=BG)
        inner.place(x=1, y=1, width=W-2, height=H-2)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = tk.Frame(inner, bg=BG1, height=76)
        hdr.pack(fill="x"); hdr.pack_propagate(False)

        cv = tk.Canvas(hdr, width=38, height=38, bg=BG1, highlightthickness=0)
        cv.place(x=16, y=14)
        cv.create_oval(2,2,36,36, fill=BG2, outline=RED, width=1)
        cv.create_text(19,20, text="🎙", font=("Segoe UI",14))

        tk.Label(hdr, text="Flow Local",
                 font=("Segoe UI",16,"bold"), bg=BG1, fg=WHITE).place(x=62,y=12)
        tk.Label(hdr, text="Offline Voice Dictation",
                 font=("Segoe UI",9), bg=BG1, fg=MUTED).place(x=63,y=38)

        # ×  minimise to tray
        def _hide(): win.withdraw()
        xl = tk.Label(hdr, text="×", font=("Segoe UI",17), bg=BG1, fg=MUTED, cursor="hand2")
        xl.place(x=W-38, y=14)
        xl.bind("<Button-1>", lambda e: _hide())
        xl.bind("<Enter>",    lambda e: xl.configure(fg=RED))
        xl.bind("<Leave>",    lambda e: xl.configure(fg=MUTED))

        # Divider
        tk.Frame(inner, bg=BG3, height=1).pack(fill="x")

        # ── Status card ───────────────────────────────────────────────────────
        sc = tk.Frame(inner, bg=BG1, pady=0)
        sc.pack(fill="x", padx=14, pady=(14,0))
        dot = tk.Canvas(sc, width=10, height=10, bg=BG1, highlightthickness=0)
        dot.pack(side="left", padx=(2,8), pady=12)
        dot.create_oval(1,1,9,9, fill=GREEN, outline="")
        tk.Label(sc, text="Ready to transcribe",
                 font=("Segoe UI",12,"bold"), bg=BG1, fg=WHITE).pack(side="left")

        # ── Hotkey card ───────────────────────────────────────────────────────
        hk_str = self.cfg.get("hotkey","windows+ctrl").replace("+"," + ").title()
        hkc = tk.Frame(inner, bg=BG2)
        hkc.pack(fill="x", padx=14, pady=(8,0))
        tk.Label(hkc, text="HOTKEY", font=("Segoe UI",7,"bold"),
                 bg=BG2, fg=MUTED).pack(anchor="w", padx=12, pady=(10,4))
        row = tk.Frame(hkc, bg=BG2)
        row.pack(anchor="w", padx=12)
        for part in hk_str.split(" + "):
            b = tk.Frame(row, bg=BG3, padx=8, pady=4)
            b.pack(side="left", padx=(0,4))
            tk.Label(b, text=part, font=("Segoe UI",9,"bold"),
                     bg=BG3, fg=OFFWHITE).pack()
        tk.Label(hkc, text="Hold to record  ·  Release to transcribe",
                 font=("Segoe UI",9), bg=BG2, fg=MUTED2).pack(
            anchor="w", padx=12, pady=(6,12))

        # ── Model card ────────────────────────────────────────────────────────
        model = self.cfg.get("whisper_model","base")
        mc = tk.Frame(inner, bg=BG2)
        mc.pack(fill="x", padx=14, pady=(8,0))
        tk.Label(mc, text="MODEL", font=("Segoe UI",7,"bold"),
                 bg=BG2, fg=MUTED).pack(anchor="w", padx=12, pady=(10,4))
        mr = tk.Frame(mc, bg=BG2)
        mr.pack(anchor="w", padx=12, pady=(0,10))
        tk.Label(mr, text=f"whisper / {model}",
                 font=("Courier",11), bg=BG2, fg=RED).pack(side="left")
        tk.Label(mr, text=" · local · offline",
                 font=("Segoe UI",9), bg=BG2, fg=MUTED).pack(side="left")

        # ── Pill preview card ─────────────────────────────────────────────────
        pc = tk.Frame(inner, bg=BG2)
        pc.pack(fill="x", padx=14, pady=(8,0))
        tk.Label(pc, text="WINDOW INDICATOR",
                 font=("Segoe UI",7,"bold"), bg=BG2, fg=MUTED).pack(
            anchor="w", padx=12, pady=(10,4))
        pill_prev = tk.Canvas(pc, width=72, height=18, bg=BG2, highlightthickness=0)
        pill_prev.pack(anchor="w", padx=12, pady=(0,10))
        r = 9
        pill_prev.create_arc(0,0,r*2,18,   start=90, extent=180, fill=BG3, outline="")
        pill_prev.create_arc(72-r*2,0,72,18,start=270,extent=180, fill=BG3, outline="")
        pill_prev.create_rectangle(r,0,72-r,18, fill=BG3, outline="")
        pill_prev.create_oval(r+2,6,r+8,12, fill=RED, outline="")
        pill_prev.create_text(44,10, text="Flow Local",
                              font=("Segoe UI",6,"bold"), fill=MUTED2)

        # ── Buttons ───────────────────────────────────────────────────────────
        bf = tk.Frame(inner, bg=BG)
        bf.pack(fill="x", padx=14, pady=16)
        pill_button(bf, "Settings", self._show_settings, full_width=True)
        pill_button(bf, "History",  self._show_history,  full_width=True)
        pill_button(bf, "Quit",     self._quit, accent=True, full_width=True)

        # Draggable header
        self._dxy = {"x":0,"y":0}
        def _dstart(e): self._dxy["x"]=e.x_root-win.winfo_x(); self._dxy["y"]=e.y_root-win.winfo_y()
        def _ddrag(e):  win.geometry(f"+{e.x_root-self._dxy['x']}+{e.y_root-self._dxy['y']}")
        hdr.bind("<ButtonPress-1>", _dstart)
        hdr.bind("<B1-Motion>",     _ddrag)

        self._panel = win

    # ── Settings ──────────────────────────────────────────────────────────────
    def _show_settings(self):
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost",True)
        win.attributes("-alpha",0.97)
        win.configure(bg=BG3)
        win.grab_set()

        W, H = 460, 560
        win.update_idletasks()
        sw = win.winfo_screenwidth(); sh = win.winfo_screenheight()
        win.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")
        win.lift()

        inner = tk.Frame(win, bg=BG)
        inner.place(x=1,y=1,width=W-2,height=H-2)

        # Header
        hdr = tk.Frame(inner, bg=BG1, height=54)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text="Settings", font=("Segoe UI",13,"bold"),
                 bg=BG1, fg=WHITE).place(x=20,y=16)
        xl = tk.Label(hdr, text="×", font=("Segoe UI",17),
                      bg=BG1, fg=MUTED, cursor="hand2")
        xl.place(x=W-38,y=12)
        xl.bind("<Button-1>", lambda e: win.destroy())
        xl.bind("<Enter>",    lambda e: xl.configure(fg=RED))
        xl.bind("<Leave>",    lambda e: xl.configure(fg=MUTED))
        tk.Frame(inner, bg=BG3, height=1).pack(fill="x")

        body = tk.Frame(inner, bg=BG)
        body.pack(fill="both", expand=True, padx=20, pady=10)

        def section(t):
            tk.Label(body, text=t, font=("Segoe UI",7,"bold"),
                     bg=BG, fg=MUTED).pack(anchor="w", pady=(14,3))
        def hint(t):
            tk.Label(body, text=t, font=("Segoe UI",8),
                     bg=BG, fg=MUTED2).pack(anchor="w", pady=(0,4))
        def entry_field(var):
            e = tk.Entry(body, textvariable=var, font=("Segoe UI",10),
                         bg=BG2, fg=WHITE, insertbackground=WHITE,
                         relief="flat", bd=0, highlightthickness=1,
                         highlightbackground=BG3, highlightcolor=RED)
            e.pack(fill="x", ipady=7)
            return e
        def combo_field(var, values):
            c = ttk.Combobox(body, textvariable=var, values=values, state="readonly",
                             font=("Segoe UI",10))
            c.pack(fill="x")
            return c
        def check_field(text, var):
            tk.Checkbutton(body, text=text, variable=var,
                           bg=BG, fg=WHITE, selectcolor=BG2,
                            activebackground=BG, activeforeground=WHITE,
                            font=("Segoe UI",9)).pack(anchor="w", pady=2)

        section("HOTKEY")
        hint("Click box then press your key combination")
        hk_frame = tk.Frame(body, bg=BG2, height=36)
        hk_frame.pack(fill="x", ipady=7)
        hk_frame.pack_propagate(False)
        
        hk_label = tk.Label(hk_frame, text=self.cfg["hotkey"],
                           font=("Segoe UI", 10), bg=BG2, fg=WHITE,
                           anchor="center")
        hk_label.pack(fill="both", expand=True)
        
        recording = [False]
        pressed_keys = set()
        key_timer = [None]
        
        mod_map = {
            'Control_L': 'ctrl', 'Control_R': 'ctrl',
            'Alt_L': 'alt', 'Alt_R': 'alt',  
            'Shift_L': 'shift', 'Shift_R': 'shift',
            'Win_L': 'windows', 'Win_R': 'windows',
            'Super_L': 'windows', 'Super_R': 'windows',
        }
        
        def get_key_name(kn, char):
            if kn in mod_map:
                return mod_map[kn]
            if kn in ('Return', 'Enter'):
                return 'enter'
            if kn == 'Escape':
                return 'escape'
            if kn == 'Tab':
                return 'tab'
            if kn == 'BackSpace':
                return 'backspace'
            if kn == 'Delete':
                return 'delete'
            if kn in ('Up', 'Down', 'Left', 'Right'):
                return kn.lower()
            if kn.startswith('F') and len(kn) <= 3:
                return kn.lower()
            if char and len(char) == 1 and char.isalnum():
                return char.lower()
            return None
        
        def format_keys():
            priority = {'ctrl': 0, 'alt': 1, 'shift': 2, 'windows': 3}
            return "+".join(sorted(pressed_keys, key=lambda x: priority.get(x, 10)))
        
        def start_recording(event=None):
            recording[0] = True
            pressed_keys.clear()
            if key_timer[0]:
                hk_label.after_cancel(key_timer[0])
            hk_label.configure(text="Press keys...", fg=RED)
            return "break"
        
        def on_key_down(event):
            if not recording[0]:
                return "break"
            
            kn = event.keysym
            char = event.char
            
            key_name = get_key_name(kn, char)
            if key_name:
                pressed_keys.add(key_name)
                hk_label.configure(text=format_keys(), fg=WHITE)
            
            if key_timer[0]:
                hk_label.after_cancel(key_timer[0])
            key_timer[0] = None
            
            return "break"
        
        def on_key_up(event):
            if not recording[0]:
                return "break"
            
            kn = event.keysym
            key_name = get_key_name(kn, event.char)
            
            if key_name and key_name not in ('ctrl', 'alt', 'shift', 'windows'):
                pressed_keys.discard(key_name)
            
            def finalize():
                key_timer[0] = None
                if recording[0] and pressed_keys:
                    hk_label.configure(text=format_keys(), fg=WHITE)
                recording[0] = False
            
            key_timer[0] = hk_label.after(150, finalize)
            return "break"
        
        def cancel_recording(event):
            recording[0] = False
            pressed_keys.clear()
            if key_timer[0]:
                hk_label.after_cancel(key_timer[0])
                key_timer[0] = None
            hk_label.configure(text=self.cfg["hotkey"], fg=WHITE)
            return "break"
        
        hk_label.bind("<Button-1>", start_recording)
        hk_label.bind("<KeyPress>", on_key_down)
        hk_label.bind("<KeyRelease>", on_key_up)
        hk_label.bind("<Escape>", cancel_recording)
        hk_label.focus_set()

        section("WHISPER MODEL")
        hint("Larger = more accurate, slower. 'base' recommended.")
        model_var = tk.StringVar(value=self.cfg["whisper_model"])
        combo_field(model_var, WHISPER_MODELS)

        section("OPTIONS")
        filler_var  = tk.BooleanVar(value=self.cfg["cleanup_fillers"])
        overlay_var = tk.BooleanVar(value=self.cfg["show_overlay"])
        check_field("Remove filler words (um, uh, like…)", filler_var)
        check_field("Show recording overlay",               overlay_var)

        section("TEXT INSERTION")
        method_var = tk.StringVar(value=self.cfg["typing_method"])
        combo_field(method_var, ["clipboard","type"])

        # Toast label (hidden until save)
        toast = tk.Label(body, text="", font=("Segoe UI",9),
                         bg=BG, fg=GREEN)
        toast.pack(anchor="w", pady=(4,0))

        def _show_toast(msg, colour=GREEN):
            toast.configure(text=msg, fg=colour)
            body.after(3000, lambda: toast.configure(text=""))

        def save():
            self._unreg()
            new_model = model_var.get()
            model_changed = new_model != self.cfg.get("whisper_model")
            self.cfg.update({
                "hotkey":          hk_label.cget("text").strip().lower(),
                "whisper_model":   new_model,
                "cleanup_fillers": filler_var.get(),
                "show_overlay":    overlay_var.get(),
                "typing_method":   method_var.get(),
            })
            save_config(self.cfg)
            self._reg_hotkey()
            # Update pill hotkey display
            self.pill.set_hotkey_str(
                self.cfg["hotkey"].replace("+"," + ").title())
            if model_changed:
                _show_toast("✓  Saved — restart app to apply new model", GREEN)
            else:
                _show_toast("✓  Settings saved", GREEN)

        tk.Frame(body, bg=BG).pack(expand=True)
        pill_button(body, "Save Settings", save, accent=True, full_width=True)

        # Draggable
        self._dxy = {"x":0,"y":0}
        hdr.bind("<ButtonPress-1>", lambda e: self._dxy.update(x=e.x_root-win.winfo_x(),y=e.y_root-win.winfo_y()))
        hdr.bind("<B1-Motion>",     lambda e: win.geometry(f"+{e.x_root-self._dxy['x']}+{e.y_root-self._dxy['y']}"))

    # ── History ───────────────────────────────────────────────────────────────
    def _show_history(self):
        if not self.history:
            win = tk.Toplevel(self.root)
            win.overrideredirect(True)
            win.attributes("-topmost", True)
            win.attributes("-alpha", 0.97)
            win.configure(bg=BG3)
            W, H = 300, 100
            win.update_idletasks()
            sw = win.winfo_screenwidth(); sh = win.winfo_screenheight()
            win.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")
            
            frame = tk.Frame(win, bg=BG3)
            frame.pack(expand=True, fill="both")
            
            tk.Label(frame, text="No transcriptions yet.",
                     font=("Segoe UI", 12), bg=BG3, fg=WHITE).pack(pady=(20, 10))
            
            btn = tk.Button(frame, text="OK", font=("Segoe UI", 10),
                           bg=BG2, fg=WHITE, relief="flat",
                           command=win.destroy)
            btn.pack()
            
            win.bind("<Button-1>", lambda e: win.destroy())
            win.lift()
            win.focus_force()
            return

        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.97)
        win.configure(bg=BG3)

        W, H = 560, 500
        win.update_idletasks()
        sw = win.winfo_screenwidth(); sh = win.winfo_screenheight()
        win.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")
        win.lift()

        inner = tk.Frame(win, bg=BG)
        inner.place(x=1,y=1,width=W-2,height=H-2)

        hdr = tk.Frame(inner, bg=BG1, height=54)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text="Transcription History",
                 font=("Segoe UI",13,"bold"), bg=BG1, fg=WHITE).place(x=20,y=16)
        xl = tk.Label(hdr, text="×", font=("Segoe UI",17),
                      bg=BG1, fg=MUTED, cursor="hand2")
        xl.place(x=W-38,y=12)
        xl.bind("<Button-1>", lambda e: win.destroy())
        xl.bind("<Enter>",    lambda e: xl.configure(fg=RED))
        xl.bind("<Leave>",    lambda e: xl.configure(fg=MUTED))
        tk.Frame(inner, bg=BG3, height=1).pack(fill="x")

        frame = tk.Frame(inner, bg=BG)
        frame.pack(fill="both", expand=True, padx=14, pady=14)

        sb = tk.Scrollbar(frame); sb.pack(side="right", fill="y")
        lb = tk.Listbox(frame, yscrollcommand=sb.set,
                        font=("Segoe UI",9), bg=BG2, fg=OFFWHITE,
                        selectbackground=RED, relief="flat", bd=0,
                        activestyle="none", highlightthickness=0)
        lb.pack(fill="both", expand=True)
        sb.config(command=lb.yview)
        for i,txt in enumerate(reversed(self.history),1):
            lb.insert("end", f"  {i:>2}.  {txt[:70]}{'…' if len(txt)>70 else ''}")

        def copy_sel():
            sel = lb.curselection()
            if sel:
                idx = len(self.history)-1-sel[0]
                pyperclip.copy(self.history[idx])
        pill_button(frame, "Copy Selected", copy_sel, full_width=True)

        self._dxy = {"x":0,"y":0}
        hdr.bind("<ButtonPress-1>", lambda e: self._dxy.update(x=e.x_root-win.winfo_x(),y=e.y_root-win.winfo_y()))
        hdr.bind("<B1-Motion>",     lambda e: win.geometry(f"+{e.x_root-self._dxy['x']}+{e.y_root-self._dxy['y']}"))

    # ── Quit ─────────────────────────────────────────────────────────────────
    def _quit(self):
        self._unreg()
        self.pill.stop()
        if self._tickray:
            try:
                self._tickray.stop()
            except Exception as e:
                print(f"Warning: Could not stop tray: {e}")
        self.root.quit(); self.root.destroy(); sys.exit(0)

    # ── Missing deps ──────────────────────────────────────────────────────────
    def _show_missing(self):
        self.root.deiconify()
        self.root.configure(bg=BG)
        self.root.title("Flow Local")
        self.root.resizable(False,False)
        sw,sh = self.root.winfo_screenwidth(),self.root.winfo_screenheight()
        self.root.geometry(f"460x340+{(sw-460)//2}+{(sh-340)//2}")
        tk.Label(self.root, text="🎙 Flow Local", font=("Segoe UI",20,"bold"),
                 bg=BG, fg=WHITE).pack(pady=(24,4))
        tk.Label(self.root, text="Missing packages — run the installer first",
                 font=("Segoe UI",10), bg=BG, fg=RED).pack()
        for pkg in MISSING:
            tk.Label(self.root, text=f"  • {pkg}", font=("Courier",10),
                     bg=BG, fg="#ff7a90").pack(anchor="w", padx=40)
        cmd = "pip install " + " ".join(MISSING)
        f = tk.Frame(self.root, bg=BG2, padx=10, pady=8)
        f.pack(padx=30, fill="x", pady=10)
        tk.Label(f, text=cmd, font=("Courier",9), bg=BG2, fg="#14ffec",
                 wraplength=400, justify="left").pack()
        def copy():
            self.root.clipboard_clear(); self.root.clipboard_append(cmd)
        pill_button(self.root,"Copy install command", copy, full_width=False).pack(pady=6)
        pill_button(self.root,"Close", self.root.destroy, accent=True, full_width=False).pack()
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
