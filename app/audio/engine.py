
import math, time, threading, queue, sys
from pathlib import Path

class _DummyFS:
    def start(self, **kw): pass
    def sfload(self, path): return 1
    def program_select(self, ch, sid, bank, preset): pass
    def cc(self, ch, ctrl, val): pass
    def noteon(self, ch, note, vel): print(f"[dummy] noteon ch{ch} {note} {vel}")
    def noteoff(self, ch, note): print(f"[dummy] noteoff ch{ch} {note}")
    def set_gain(self, g): pass
    def reverb_on(self): pass
    def reverb_off(self): pass
    @property
    def settings(self): return {}

import os, sys
from pathlib import Path

# Forzar PATH para que Windows encuentre las DLLs
dll_dir = Path(__file__).resolve().parents[2] / "fluidsynth_dlls"
os.environ["PATH"] = str(dll_dir) + os.pathsep + os.environ["PATH"]

try:
    import fluidsynth
except Exception:
    fluidsynth = None

class SoundEngine:
    """API compatible con la legacy, pero segura si no hay FluidSynth."""
    def __init__(self, sf2: Path):
        self.fs = None
        self.q = queue.Queue()
        self.ok = threading.Event()
        self.master_db = 20.0
        self.master_linear = 10 ** (self.master_db/20.0)
        self.limiter_enabled = False
        self.limiter_ceiling = 0.94
        self.velocity_gain = 3.0
        self.gamma = 1.0
        self.reverb_roomsize = 0.70
        self.reverb_damping = 0.20
        self.reverb_width = 0.90
        self.reverb_level = 0.60
        self.reverb_send = 1.0
        self.sfid = None
        threading.Thread(target=self._setup, args=(sf2,), daemon=True).start()
        threading.Thread(target=self._render, daemon=True).start()
        time.sleep(0.3)

    def _setup(self, sf2):
        if fluidsynth is None:
            self.fs = _DummyFS()
        else:
            self.fs = fluidsynth.Synth()
            self.fs.start(driver="dsound" if sys.platform.startswith("win") else "alsa")
        self.sfid = self.fs.sfload(str(sf2))
        self.fs.program_select(0, self.sfid, 0, 0)
        for ch in range(16):
            try:
                self.fs.cc(ch, 7, 127)
                self.fs.cc(ch, 11, 127)
            except Exception:
                pass
        self.ok.set()

    def _render(self):
        while True:
            typ, note, vel = self.q.get()
            if not self.ok.is_set():
                continue
            if typ == "on":
                for ch in range(1):
                    try: self.fs.noteon(ch, note, vel)
                    except Exception: pass
            else:
                for ch in range(1):
                    try: self.fs.noteoff(ch, note)
                    except Exception: pass

    def disparar(self, msg):
        t = getattr(msg, "type", None)
        if t == "control_change":
            try: self.fs.cc(getattr(msg, "channel", 0), msg.control, msg.value)
            except Exception: pass
            return
        if t == "note_on" and getattr(msg, "velocity", 0):
            x = max(0.0, min(1.0, msg.velocity / 127.0))
            shaped = (x ** self.gamma) * 127.0
            master_scale = self.master_linear if self.master_linear < 1.0 else 1.0
            v = int(max(1, min(127, shaped * self.velocity_gain * master_scale)))
            if self.limiter_enabled:
                ceiling = int(max(1, min(127, round(self.limiter_ceiling * 127))))
                if v > ceiling: v = ceiling
            self.q.put(("on", msg.note, v))
        elif t in ("note_off", "note_on"):
            self.q.put(("off", msg.note, 0))

    def set_reverb_active(self, active: bool): pass
    def set_reverb(self, roomsize=None, level=None, damping=None, width=None):
        if roomsize is not None: self.reverb_roomsize = float(roomsize)
        if level is not None: self.reverb_level = float(level)
        if damping is not None: self.reverb_damping = float(damping)
        if width is not None: self.reverb_width = float(width)
    def set_reverb_send(self, amount: float, *, remember: bool=True): self.reverb_send = float(amount)
    def set_master_gain_db(self, db: float):
        self.master_db = float(db); self.master_linear = 10 ** (self.master_db/20.0)
    def set_limiter_enabled(self, enabled: bool): self.limiter_enabled = bool(enabled)
    def load_sf2_live(self, new_sf2: Path, bank: int = 0, preset: int = 0):
        self.sfid = self.fs.sfload(str(new_sf2)); self.fs.program_select(0, self.sfid, bank, preset)
