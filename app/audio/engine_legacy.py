"""Legacy SoundEngine ported from the original TIMBAL 2.0 app."""
from __future__ import annotations

import os
import math
import queue
import threading
import time
from pathlib import Path

from mido import Message

from app.audio.bootstrap_fluidsynth import bootstrap

fluidsynth = bootstrap()


def _audio_setting(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default

class SoundEngine:
    def __init__(self, sf2: Path):
        self.fs = None
        self.q = queue.Queue()
        self.ok = threading.Event()
        self.error = None
        self.master_db = 20.0  # volumen inicial (dB) (antes -6.0)
        self.max_master_db = 30.0
        self._extra_boost_db = 0.0
        self._gen_attenuation = None
        self._last_gain_linear = None
        self._last_extra_db = None
        self.limiter_enabled = False
        self.limiter_ceiling = 0.94
        self.master_linear = math.pow(10.0, self.master_db / 20.0)
        self.max_layers = 4
        self.layer_count = 1
        self.gamma = 1.0
        # Ganancia de velocidad "plana" por defecto.
        # El control de Boost de la UI la ajusta a partir de este valor.
        self.velocity_gain = 1.0
        self.reverb_roomsize = 0.70
        self.reverb_damping = 0.20
        self.reverb_width = 0.90
        self.reverb_level = 0.60
        self.reverb_send = 1.0
        self._reverb_send_prev = self.reverb_send
        self.sfid = None
        self.lock = threading.Lock()
        # Verificar que el archivo SF2 existe
        if not sf2.exists():
            raise FileNotFoundError(f"Archivo SF2 no encontrado: {sf2}")

        print(f"ÃƒÂ°Ã…Â¸Ã…Â½Ã‚Âµ Cargando SoundFont: {sf2}")

        threading.Thread(target=self._setup, args=(sf2,), daemon=True).start()
        threading.Thread(target=self._render, daemon=True).start()

        # Esperar un momento para que se inicialice
        time.sleep(1)

        if self.error:
            raise Exception(f"Error inicializando audio: {self.error}")

    def _setup(self, sf2):
        try:
            samplerate = _audio_setting("TIMBAL_FS_SAMPLE_RATE", 48000)
            period_size = _audio_setting("TIMBAL_FS_PERIOD_SIZE", 64)
            periods = _audio_setting("TIMBAL_FS_PERIODS", 2)
            print(
                f"[audio] Fluidsynth config: samplerate={samplerate} "
                f"period_size={period_size} periods={periods}"
            )
            self.fs = fluidsynth.Synth(
                gain=0.2,
                samplerate=samplerate,
                **{
                    "audio.period-size": period_size,
                    "audio.periods": periods,
                },
            )
            gen_mod = getattr(fluidsynth, 'generator', None)
            if gen_mod:
                try:
                    self._gen_attenuation = getattr(gen_mod, 'ATTENUATION')
                except Exception:
                    self._gen_attenuation = None
            print("ÃƒÂ¢Ã…Â“Ã¢Â€Â¦ Sintetizador creado")

            # Probar diferentes drivers
            drivers = ["wasapi", "dsound", "winmm", "alsa", "pulse", "jack"]
            driver_loaded = False

            for drv in drivers:
                try:
                    self.fs.start(driver=drv)
                    print(f"ÃƒÂ¢Ã…Â“Ã¢Â€Â¦ Driver de audio cargado: {drv}")
                    driver_loaded = True
                    break
                except Exception as e:
                    print(f"ÃƒÂ¢Ã…Â¡Ã‚Â  Driver {drv} fallÃƒÂƒÃ‚Â³: {e}")

            if not driver_loaded:
                raise Exception("No se pudo cargar ningÃƒÂƒÃ‚Âºn driver de audio")

            # ---- VOLUMEN AL MÃƒÂƒÃ‚Â�XIMO (compat con versiones viejas) ----
            try:
                # 1) Si existiera set_gain(), usarlo
                if hasattr(self.fs, "set_gain"):
                    try:
                        self.fs.set_gain(10.0)  # 10.0 = tope de FluidSynth
                        print("ÃƒÂ°Ã…Â¸Ã¢Â€Â�Ã…Â  Gain por set_gain=10.0")
                    except Exception:
                        pass

                # 2) Si el sintetizador expone settings internos, probar setear synth.gain
                st = getattr(self.fs, "settings", None)
                if st:
                    try:
                        # algunas versiones aceptan interfaz tipo dict
                        st["synth.gain"] = 10.0
                        print("ÃƒÂ°Ã…Â¸Ã¢Â€Â�Ã…Â  Gain por settings['synth.gain']=10.0")
                    except Exception:
                        try:
                            # otras requieren .setnum()
                            st.setnum("synth.gain", 10.0)
                            print("ÃƒÂ°Ã…Â¸Ã¢Â€Â�Ã…Â  Gain por settings.setnum('synth.gain',10.0)")
                        except Exception:
                            pass

                # 3) SIEMPRE: asegurar volumen/expresiÃƒÂƒÃ‚Â³n MIDI al tope
                for ch in range(16):
                    try:
                        self.fs.cc(ch, 7, 127)  # CC7 Volume
                        self.fs.cc(ch, 11, 127)  # CC11 Expression
                    except Exception:
                        pass

                self.set_reverb_send(self.reverb_send, remember=False)

            except Exception as _e:
                print("ÃƒÂ¢Ã…Â¡Ã‚Â  No se pudo forzar gain por API; quedan CC7/CC11 a 127.")

            # Activar reverb predeterminada usando los valores almacenados
            try:
                self.set_reverb_active(True)
                self.set_reverb(
                    roomsize=self.reverb_roomsize,
                    level=self.reverb_level,
                    damping=self.reverb_damping,
                    width=self.reverb_width,
                )
            except Exception:
                pass

            # Cargar SoundFont
            sid = self.fs.sfload(str(sf2))
            if sid == -1:
                raise Exception("Error cargando SoundFont")

            self.sfid = sid
            self.fs.program_select(0, sid, 0, 0)
            for ch in range(1, getattr(self, 'max_layers', 1)):
                try:
                    self.fs.program_select(ch, sid, 0, 0)
                    self.fs.cc(ch, 7, 127)
                    self.fs.cc(ch, 11, 127)
                except Exception:
                    pass
            self.set_reverb_send(self.reverb_send, remember=False)
            self.set_reverb_active(self.reverb_level > 0)
            print("ÃƒÂ¢Ã…Â“Ã¢Â€Â¦ SoundFont cargado correctamente")
            with self.lock:
                self._apply_master_gain_locked()

            self.ok.set()

        except Exception as e:
            self.error = str(e)
            print(f"ÃƒÂ¢Ã‚Â�Ã…Â’ Error en setup de audio: {e}")

    def _render(self):
        while True:
            try:
                typ, note, vel = self.q.get()
                if not self.ok.is_set():
                    continue

                if self.fs is None:
                    continue

                if typ == "on":
                    layers = getattr(self, 'layer_count', 1)
                    for ch in range(layers):
                        try:
                            self.fs.noteon(ch, note, vel)
                        except Exception:
                            pass
                else:
                    # noteoff de FluidSynth no recibe velocidad
                    for ch in range(getattr(self, 'max_layers', getattr(self, 'layer_count', 1))):
                        try:
                            self.fs.noteoff(ch, note)
                        except Exception:
                            pass

            except Exception as e:
                print(f"ÃƒÂ¢Ã…Â¡Ã‚Â  Error en render: {e}")

    def set_master_gain_db(self, db: float):
        try:
            value = float(db)
        except (TypeError, ValueError):
            return
        value = max(-60.0, min(self.max_master_db, value))
        with self.lock:
            prev = self.master_db
            self.master_db = value
            self.master_linear = math.pow(10.0, self.master_db / 20.0)
            self._apply_master_gain_locked()
        if abs(prev - self.master_db) > 0.05:
            print(f"Master gain ajustado a {self.master_db:.1f} dB")

    def set_limiter_enabled(self, enabled: bool):
        with self.lock:
            prev = self.limiter_enabled
            self.limiter_enabled = bool(enabled)
        if prev != self.limiter_enabled:
            estado = 'activado' if self.limiter_enabled else 'desactivado'
            print(f"Limitador {estado}")

    def _update_layer_count(self, count: int):
        count = int(max(1, min(self.max_layers, count)))
        if count == getattr(self, 'layer_count', 1):
            return
        self.layer_count = count
        print(f'[MASTER] capas activas: {self.layer_count}')

    def _apply_master_gain_locked(self):
        fs = self.fs
        if not fs:
            return
        target_db = float(self.master_db)
        desired_amp = max(0.001, math.pow(10.0, target_db / 20.0))
        self.master_linear = desired_amp
        base_gain = min(desired_amp, 10.0)
        if base_gain <= 0.0:
            base_gain = 0.001
        if self._last_gain_linear is None or abs(self._last_gain_linear - base_gain) > 1e-3:
            try:
                if hasattr(fs, 'set_gain'):
                    fs.set_gain(base_gain)
                    print(f'[MASTER] set_gain -> {base_gain:.3f}')
                else:
                    st = getattr(fs, 'settings', None)
                    if st is not None:
                        try:
                            st['synth.gain'] = base_gain
                            print(f'[MASTER] settings[''synth.gain''] = {base_gain:.3f}')
                        except Exception:
                            st.setnum('synth.gain', float(base_gain))
                            print(f'[MASTER] settings.setnum(synth.gain, {base_gain:.3f})')
            except Exception:
                pass
            self._last_gain_linear = base_gain
        layer_mult = max(1.0, desired_amp / base_gain)
        layer_count = int(math.ceil(layer_mult))
        self._update_layer_count(layer_count)
        extra_db = max(0.0, target_db - 20.0)
        self._set_extra_boost_db(extra_db)


    def _set_extra_boost_db(self, extra_db: float):
        if self._gen_attenuation is None or not hasattr(self.fs, 'set_gen'):
            if self._gen_attenuation is None:
                print('[MASTER] ATTENUATION generator no disponible')
            elif not hasattr(self.fs, 'set_gen'):
                print('[MASTER] set_gen no soportado en este Fluidsynth')
            self._extra_boost_db = 0.0
            self._last_extra_db = 0.0
            return
        max_extra = max(0.0, self.max_master_db - 20.0)
        bounded = max(0.0, min(max_extra, extra_db))
        if self._last_extra_db is not None and abs(self._last_extra_db - bounded) < 0.1:
            return
        value = -bounded * 10.0
        try:
            self.fs.set_gen(0, self._gen_attenuation, value)
            print(f'[MASTER] extra boost {bounded:.1f} dB -> set_gen ATTENUATION={value:.1f}')
        except Exception as e:
            print(f'[MASTER] extra boost fall?: {e}')
        self._extra_boost_db = bounded
        self._last_extra_db = bounded

    def set_reverb(self, roomsize=None, level=None, damping=None, width=None):
        if roomsize is not None:
            self.reverb_roomsize = max(0.0, min(1.0, float(roomsize)))
        if level is not None:
            self.reverb_level = max(0.0, min(1.0, float(level)))
        if damping is not None:
            self.reverb_damping = max(0.0, min(1.0, float(damping)))
        if width is not None:
            self.reverb_width = max(0.0, min(1.0, float(width)))

        if not self.fs:
            return

        rs = self.reverb_roomsize
        dp = self.reverb_damping
        wd = self.reverb_width
        lv = self.reverb_level

        try:
            if hasattr(self.fs, "set_reverb"):
                self.fs.set_reverb(rs, dp, wd, lv)
                return
        except Exception:
            pass

        st2 = getattr(self.fs, "settings", None)
        if not st2:
            return

        def _set(k, v):
            try:
                try:
                    st2[k] = v
                except Exception:
                    st2.setnum(k, float(v)) if isinstance(v, float) else st2.setint(k, int(v))
            except Exception:
                pass

        _set("synth.reverb.room-size", rs)
        _set("synth.reverb.damp", dp)
        _set("synth.reverb.width", wd)
        _set("synth.reverb.level", lv)

    def set_reverb_send(self, amount: float, *, remember: bool = True):
        try:
            target = float(amount)
        except (TypeError, ValueError):
            return
        target = max(0.0, min(1.0, target))
        if remember:
            self.reverb_send = target
        if not self.fs:
            return
        try:
            val = int(round(target * 127))
            for ch in range(16):
                self.fs.cc(ch, 91, val)
        except Exception:
            pass

    def load_sf2_live(self, new_sf2: Path, bank: int = 0, preset: int = 0):
        if not self.fs:
            raise RuntimeError("Synth no inicializado")
        p = Path(new_sf2)
        if not p.exists():
            raise FileNotFoundError(f"SF2 no encontrado: {new_sf2}")
        sid = self.fs.sfload(str(p))
        if sid == -1:
            raise RuntimeError("No se pudo cargar el nuevo SoundFont")
        try:
            self.fs.program_select(0, sid, bank, preset)
        except Exception:
            pass
        for ch in range(1, getattr(self, 'max_layers', 1)):
            try:
                self.fs.program_select(ch, sid, bank, preset)
                self.fs.cc(ch, 7, 127)
                self.fs.cc(ch, 11, 127)
            except Exception:
                pass
        if self.sfid is not None and self.sfid != sid and hasattr(self.fs, "sfunload"):
            try:
                self.fs.sfunload(self.sfid, True)
            except Exception:
                pass
        self.sfid = sid
        self.set_reverb_send(self.reverb_send, remember=False)
        self.set_reverb_active(self.reverb_level > 0)
        with self.lock:
            self._apply_master_gain_locked()

    def set_reverb_active(self, active: bool):
        if active:
            restore = self.reverb_send if self.reverb_send > 0 else getattr(self, '_reverb_send_prev', 1.0)
            if restore <= 0:
                restore = 1.0
            self.set_reverb_send(restore, remember=True)
            self._reverb_send_prev = self.reverb_send
        else:
            self._reverb_send_prev = self.reverb_send if self.reverb_send > 0 else getattr(self, '_reverb_send_prev', 1.0)
            self.set_reverb_send(0.0, remember=True)
        if not self.fs:
            return
        try:
            if active and hasattr(self.fs, 'reverb_on'):
                self.fs.reverb_on()
            elif not active and hasattr(self.fs, 'reverb_off'):
                self.fs.reverb_off()
        except Exception:
            pass
        st = getattr(self.fs, 'settings', None)
        if st:
            try:
                st['synth.reverb.active'] = 1 if active else 0
            except Exception:
                try:
                    st.setint('synth.reverb.active', 1 if active else 0)
                except Exception:
                    pass

    def disparar(self, msg: Message):
        try:
            if msg.type == "control_change":  # ÃƒÂ¢Ã¢Â€Â Ã‚Â� NUEVO
                self.fs.cc(getattr(msg, "channel", 0), msg.control, msg.value);
                return
            if msg.type == "note_on" and msg.velocity:
                x = max(0.0, min(1.0, msg.velocity / 127.0))
                shaped = pow(x, self.gamma) * 127.0
                master_scale = self.master_linear if self.master_linear < 1.0 else 1.0
                v = int(max(1, min(127, shaped * self.velocity_gain * master_scale)))
                if self.limiter_enabled:
                    ceiling = int(max(1, min(127, round(self.limiter_ceiling * 127))))
                    if v > ceiling:
                        v = ceiling
                # DEBUG volume tracing
                print(f"[VOL] note {msg.note} vel_in={msg.velocity} -> vel_out={v} (master={self.master_db:.1f} dB, scale={master_scale:.3f}, gain={self.master_linear:.3f})")
                self.q.put(("on", msg.note, v))

            elif msg.type in ("note_off", "note_on"):
                self.q.put(("off", msg.note, 0))
        except Exception as e:
            print(f"ÃƒÂ¢Ã…Â¡Ã‚Â  Error disparando nota: {e}")
