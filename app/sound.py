# SwitchMorse Windows - sound.py
# Beeps through the computer's speakers: a tone while a dot or dash is held,
# a short blip when an action fires or the group changes. Off unless chosen in
# the window's right-click menu (Sound).
#
# The engine is AeroMorse Display's (aeromorse_display.py, WinSound): each tone
# is a tiny ready-made clip - a whole number of waves, about 10 ms - that
# Windows repeats by itself for as long as the press lasts, so it cannot
# crackle when the computer is busy, and "tone off" stops it within a few ms.
import math
import threading
import time

DOT_FREQ = 1200          # same pitches as AeroMorse (BEEP_DOT_FREQ / BEEP_DASH_FREQ)
DASH_FREQ = 800
ACTION_FREQ = 1050       # CONFIRM_FREQ, 60 ms
GROUP_FREQ = 550         # GROUP_FREQ, 140 ms


class Sound:
    LEVELS = {"off": 0.0, "quiet": 0.10, "medium": 0.30, "loud": 0.85}
    RATE = 44100

    def __init__(self, level="off"):
        self.level = level if level in self.LEVELS else "off"
        self.ok = False
        self._dev = None
        self._mm = None
        self._clips = {}                  # (kind, freq, ms, level) -> [header, samples]
        self._lock = threading.Lock()
        self._th = None
        self._busy = 0.0                  # until when something sounds (inf = a held tone)

    # ---- set-up ----------------------------------------------------------------------
    def prime(self):
        """Open the sound device now (about 0.4 s), so the first beep isn't late."""
        if self.level != "off" and self._th is None:
            self._th = threading.Thread(target=self._open, daemon=True)
            self._th.start()

    def _open(self):
        import ctypes
        from ctypes import wintypes

        class WAVEFORMATEX(ctypes.Structure):
            _fields_ = [("wFormatTag", wintypes.WORD), ("nChannels", wintypes.WORD),
                        ("nSamplesPerSec", wintypes.DWORD), ("nAvgBytesPerSec", wintypes.DWORD),
                        ("nBlockAlign", wintypes.WORD), ("wBitsPerSample", wintypes.WORD),
                        ("cbSize", wintypes.WORD)]

        class WAVEHDR(ctypes.Structure):
            _fields_ = [("lpData", ctypes.c_void_p), ("dwBufferLength", wintypes.DWORD),
                        ("dwBytesRecorded", wintypes.DWORD), ("dwUser", ctypes.c_size_t),
                        ("dwFlags", wintypes.DWORD), ("dwLoops", wintypes.DWORD),
                        ("lpNext", ctypes.c_void_p), ("reserved", ctypes.c_size_t)]
        self._ct, self._HDR = ctypes, WAVEHDR
        try:
            mm = ctypes.windll.winmm
            fmt = WAVEFORMATEX(1, 1, self.RATE, self.RATE * 2, 2, 16, 0)
            dev = ctypes.c_void_p()
            if mm.waveOutOpen(ctypes.byref(dev), 0xFFFFFFFF, ctypes.byref(fmt), None, None, 0):
                return
        except Exception:
            return
        self._mm, self._dev = mm, dev
        self.ok = True

    # ---- clips ---------------------------------------------------------------------------
    def _make(self, kind, freq, ms):
        ct = self._ct
        amp = 32767 * self.LEVELS.get(self.level, 0.0)
        freq = max(100, min(4000, freq))
        if kind == "loop":
            waves = max(1, int(round(freq * 0.010)))
            n = int(round(waves * self.RATE / float(freq)))
            w = 2 * math.pi * waves / n
            fade = 0
        else:
            n = max(1, int(self.RATE * ms / 1000.0))
            w = 2 * math.pi * freq / self.RATE
            fade = min(int(self.RATE * 0.004), n // 2)
        buf = (ct.c_short * n)()
        for i in range(n):
            g = min(1.0, i / float(fade), (n - 1 - i) / float(fade)) if fade else 1.0
            buf[i] = int(amp * g * math.sin(w * i))
        hdr = self._HDR(ct.addressof(buf), n * 2, 0, 0, 0, 0, None, 0)
        self._mm.waveOutPrepareHeader(self._dev, ct.byref(hdr), ct.sizeof(hdr))
        return [hdr, buf]

    def _free_clip(self, kind, freq, ms):
        pool = self._clips.setdefault((kind, freq, ms, self.level), [])
        for c in pool:
            if not (c[0].dwFlags & 0x10):                     # WHDR_INQUEUE
                return c
        if len(pool) < 6:
            c = self._make(kind, freq, ms)
            pool.append(c)
            return c
        return None

    def _clear(self):
        if self._busy > time.time():
            self._mm.waveOutReset(self._dev)
        self._busy = 0.0

    # ---- what the program calls ------------------------------------------------------------
    def _ready(self):
        if self.level == "off":
            return False
        if not self.ok:
            self.prime()
            return False                                      # still opening: skip this one
        return True

    def tone(self, freq):
        """Start a tone that lasts until stop()."""
        if not self._ready():
            return
        try:
            with self._lock:
                self._clear()
                c = self._free_clip("loop", freq, 0)
                if c is None:
                    return
                c[0].dwFlags = (c[0].dwFlags | 0x4 | 0x8) & ~0x1     # BEGINLOOP | ENDLOOP
                c[0].dwLoops = 0x7FFFFFFF
                self._busy = float("inf")
                self._mm.waveOutWrite(self._dev, self._ct.byref(c[0]), self._ct.sizeof(c[0]))
        except Exception:
            pass

    def stop(self):
        if self.ok:
            try:
                with self._lock:
                    self._clear()
            except Exception:
                pass

    def blip(self, freq, ms):
        """A short beep (action fired, group changed)."""
        if not self._ready():
            return
        try:
            with self._lock:
                self._clear()
                c = self._free_clip("blip", freq, max(20, ms))
                if c is None:
                    return
                c[0].dwFlags &= ~0x1
                self._busy = time.time() + ms / 1000.0 + 0.05
                self._mm.waveOutWrite(self._dev, self._ct.byref(c[0]), self._ct.sizeof(c[0]))
        except Exception:
            pass

    def set_level(self, level):
        self.stop()
        self.level = level if level in self.LEVELS else "off"
        self.prime()
