

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Timbal Digital â€“ GUI + Fluidsynth + MIDI
Compatible: Windows 10/11 x64 Â· Python 3.9â€“3.12
"""

# ------------------------------------------------------------------
# 1 Â· Fluidsynth  â€”  carga mejorada con mÃºltiples rutas
# ------------------------------------------------------------------
from pathlib import Path
import os, sys, json, queue, threading, time, math

# ConfiguraciÃ³n mÃ¡s robusta de las DLLs
DLL_DIR = Path(__file__).parent / "fluidsynth_dlls"
DLL_DLL = DLL_DIR / "libfluidsynth-3.dll"

# AÃ±adir el directorio DLL al PATH del sistema
if str(DLL_DIR) not in os.environ.get("PATH", ""):
    os.environ["PATH"] = str(DLL_DIR) + os.pathsep + os.environ.get("PATH", "")

# AÃ±adir directorio DLL (Windows 10/11)
try:
    os.add_dll_directory(str(DLL_DIR))
except (AttributeError, OSError) as e:
    print(f"âš  No se pudo aÃ±adir directorio DLL: {e}")

# Configurar variable de entorno para pyfluidsynth
os.environ["PYFLUIDSYNTH_LIB"] = str(DLL_DLL)

# Verificar que la DLL existe antes de continuar
if not DLL_DLL.exists():
    print(f"âŒ Error: No se encuentra {DLL_DLL}")
    print(f"   Archivos en {DLL_DIR}:")
    for f in DLL_DIR.glob("*.dll"):
        print(f"   - {f.name}")
    sys.exit(1)

print(f"ðŸ” Buscando FluidSynth en: {DLL_DLL}")
print(f"   Archivo existe: {DLL_DLL.exists()}")

# Intentar diferentes nombres de DLL comunes
POSSIBLE_DLLS = [
    "libfluidsynth-3.dll",
    "libfluidsynth.dll",
    "fluidsynth.dll",
    "libfluidsynth-2.dll"
]

dll_found = None
for dll_name in POSSIBLE_DLLS:
    dll_path = DLL_DIR / dll_name
    if dll_path.exists():
        dll_found = dll_path
        os.environ["PYFLUIDSYNTH_LIB"] = str(dll_path)
        print(f"âœ… Usando DLL: {dll_name}")
        break

if not dll_found:
    print("âŒ No se encontrÃ³ ninguna DLL de FluidSynth vÃ¡lida")
    print("   Archivos .dll disponibles:")
    for f in DLL_DIR.glob("*.dll"):
        print(f"   - {f.name}")
    sys.exit(1)


# FunciÃ³n para verificar dependencias de DLL
def check_dll_dependencies(dll_path):
    import ctypes
    from ctypes import wintypes

    # Cargar kernel32 para usar SetDllDirectory
    kernel32 = ctypes.windll.kernel32
    kernel32.SetDllDirectoryW.argtypes = [wintypes.LPCWSTR]
    kernel32.SetDllDirectoryW.restype = wintypes.BOOL

    # Establecer directorio de bÃºsqueda de DLLs
    kernel32.SetDllDirectoryW(str(DLL_DIR))

    try:
        # Intentar cargar con LOAD_WITH_ALTERED_SEARCH_PATH
        LOAD_WITH_ALTERED_SEARCH_PATH = 0x00000008
        handle = kernel32.LoadLibraryExW(
            str(dll_path),
            None,
            LOAD_WITH_ALTERED_SEARCH_PATH
        )
        if handle:
            kernel32.FreeLibrary(handle)
            return True, "OK"
        else:
            error_code = kernel32.GetLastError()
            return False, f"Error code: {error_code}"
    except Exception as e:
        return False, str(e)


# Verificar dependencias comunes de FluidSynth
print("ðŸ” Verificando dependencias de FluidSynth...")
common_deps = [
    "libglib-2.0-0.dll",
    "libgobject-2.0-0.dll",
    "libgthread-2.0-0.dll",
    "libintl-8.dll",
    "libinstpatch-2.dll",
    "sndfile.dll"
]

missing_deps = []
for dep in common_deps:
    dep_path = DLL_DIR / dep
    if dep_path.exists():
        print(f"   âœ… {dep}")
    else:
        print(f"   âŒ {dep} - FALTA")
        missing_deps.append(dep)

if missing_deps:
    print(f"\nâš  Dependencias faltantes: {', '.join(missing_deps)}")
    print("ðŸ’¡ Posibles soluciones:")
    print("   1. Descargar FluidSynth completo desde: https://github.com/FluidSynth/fluidsynth/releases")
    print("   2. Copiar todas las DLLs del paquete oficial")
    print("   3. Instalar usando conda: conda install -c conda-forge fluidsynth")

# Cargar ctypes manualmente para debug con mejor manejo
success, error_msg = check_dll_dependencies(dll_found)
if success:
    print(f"âœ… DLL cargada exitosamente con dependencias")
else:
    print(f"âŒ Error cargando DLL: {error_msg}")

    # Intentar mÃ©todo alternativo
    print("\nðŸ”„ Intentando mÃ©todo alternativo...")
    try:
        import ctypes

        # Cambiar al directorio de DLLs temporalmente
        original_cwd = os.getcwd()
        os.chdir(str(DLL_DIR))

        test_lib = ctypes.CDLL(str(dll_found.name))  # Solo el nombre, no la ruta completa
        print(f"âœ… DLL cargada con mÃ©todo alternativo")

        os.chdir(original_cwd)
    except Exception as e2:
        print(f"âŒ MÃ©todo alternativo tambiÃ©n fallÃ³: {e2}")
        os.chdir(original_cwd)

        print("\nðŸ’¡ SoluciÃ³n recomendada:")
        print("   Descargar FluidSynth completo con todas las dependencias")
        print("   desde: https://github.com/FluidSynth/fluidsynth/releases")
        sys.exit(1)

try:
    import fluidsynth

    print("âœ… MÃ³dulo fluidsynth importado correctamente")
except ImportError as e:
    print(f"âŒ Error importando fluidsynth: {e}")
    print("ðŸ’¡ Soluciones posibles:")
    print("   1. Instalar: pip install pyFluidSynth")
    print("   2. Verificar que todas las DLLs dependientes estÃ©n presentes")
    print("   3. Usar conda: conda install -c conda-forge fluidsynth")
    sys.exit(1)

# ------------------------------------------------------------------
# 2 Â· dependencias GUI / MIDI / Serial
# ------------------------------------------------------------------
try:
    from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLabel,
                                 QGridLayout, QPushButton, QStackedWidget, QComboBox,
                                 QDialog, QDialogButtonBox, QHBoxLayout, QFileDialog,
                                 QMessageBox, QSlider)
    from PyQt5.QtGui import QPalette, QColor
    from PyQt5.QtCore import Qt, QTimer
except ImportError as e:
    print(f"âŒ Error importando PyQt5: {e}")
    print("ðŸ’¡ Instalar con: pip install PyQt5")
    sys.exit(1)

try:
    import serial, serial.tools.list_ports
except ImportError as e:
    print(f"âŒ Error importando serial: {e}")
    print("ðŸ’¡ Instalar con: pip install pyserial")
    sys.exit(1)

try:
    import mido
    from mido import Message
except ImportError as e:
    print(f"âŒ Error importando mido: {e}")
    print("ðŸ’¡ Instalar con: pip install mido")
    sys.exit(1)

try:
    mido.set_backend('mido.backends.rtmidi')
except Exception:
    pass



# ------------------------------------------------------------------
# 3 · Configuración y persistencia simple
# ------------------------------------------------------------------

def _app_config_dir() -> Path:
    appdata = os.getenv('APPDATA')
    base = Path(appdata) if appdata else (Path.home() / '.timbal_app')
    d = base / 'TimbalApp'
    d.mkdir(parents=True, exist_ok=True)
    return d

CONFIG_PATH = _app_config_dir() / 'config.json'


def load_config() -> dict:
    try:
        if CONFIG_PATH.exists():
            return json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
    except Exception:
        pass
    return {}


def save_config(cfg: dict) -> None:
    try:
        CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        print('Aviso: no pude guardar la configuración.')

# ------------------------------------------------------------------
# 3 Â· widgets auxiliares
# ------------------------------------------------------------------
class NoteSelectorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Seleccionar nota")
        lay = QVBoxLayout(self)
        self.combo = QComboBox()
        self.combo.addItems([f"{n}{o}"
                             for o in range(0, 9) for n in "C C# D D# E F F# G G# A A# B".split()])
        lay.addWidget(self.combo)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept);
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def nota(self): return self.combo.currentText()



class Vu(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedWidth(50)
        lay = QVBoxLayout(self)
        self.barras = []
        for _ in range(10):
            lbl = QLabel()
            lbl.setFixedHeight(10)
            lbl.setStyleSheet("background:#DDD;")
            lay.addWidget(lbl)
            self.barras.append(lbl)
        # Suavizado del VU (sube r?pido, cae m?s lento)
        self._level = 0.0
        self._alpha_up = 0.6
        self._alpha_down = 0.15
        self._peak_index = -1
        self._peak_hold = 0
        self._peak_hold_ticks = 8
        self._decay_step = 3.0
        self._timer = QTimer(self)
        self._timer.setInterval(60)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    @staticmethod
    def _color_for(idx: int) -> str:
        if idx < 3:
            return "#4CAF50"
        if idx < 6:
            return "#FFFF00"
        return "#FF0000"

    def _render_barras(self, activos: int):
        peak = self._peak_index
        total = len(self.barras)
        for idx, barra in enumerate(reversed(self.barras)):
            if idx < activos:
                barra.setStyleSheet(f"background:{self._color_for(idx)}")
            elif peak >= 0 and idx == peak:
                barra.setStyleSheet("background:#FFA726")
            else:
                barra.setStyleSheet("background:#DDD")

    def actualizar(self, val_0_127: int):
        val = max(0, min(127, int(val_0_127)))
        if val >= self._level:
            self._level = self._alpha_up * val + (1 - self._alpha_up) * self._level
        else:
            self._level = self._alpha_down * val + (1 - self._alpha_down) * self._level
        activos = int(self._level // 13)
        if activos > 0:
            peak_candidate = min(len(self.barras) - 1, activos - 1)
            if peak_candidate >= self._peak_index:
                self._peak_index = peak_candidate
                self._peak_hold = self._peak_hold_ticks
        self._render_barras(activos)

    def _tick(self):
        if self._level > 0:
            self._level = max(0.0, self._level - self._decay_step)
        activos = int(self._level // 13)
        if self._peak_index >= 0:
            if self._peak_hold > 0:
                self._peak_hold -= 1
            else:
                self._peak_index -= 1
                self._peak_hold = self._peak_hold_ticks // 2
                if self._peak_index < 0:
                    self._peak_index = -1
        self._render_barras(activos)



# ------------------------------------------------------------------
# 4 Â· motor de audio - con manejo de errores mejorado
# ------------------------------------------------------------------
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
        self.velocity_gain = 3.0
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

        print(f"ðŸŽµ Cargando SoundFont: {sf2}")

        threading.Thread(target=self._setup, args=(sf2,), daemon=True).start()
        threading.Thread(target=self._render, daemon=True).start()

        # Esperar un momento para que se inicialice
        time.sleep(1)

        if self.error:
            raise Exception(f"Error inicializando audio: {self.error}")

    def _setup(self, sf2):
        try:
            self.fs = fluidsynth.Synth()
            gen_mod = getattr(fluidsynth, 'generator', None)
            if gen_mod:
                try:
                    self._gen_attenuation = getattr(gen_mod, 'ATTENUATION')
                except Exception:
                    self._gen_attenuation = None
            print("âœ… Sintetizador creado")

            # Probar diferentes drivers
            drivers = ["wasapi", "dsound", "winmm", "alsa", "pulse", "jack"]
            driver_loaded = False

            for drv in drivers:
                try:
                    self.fs.start(driver=drv)
                    print(f"âœ… Driver de audio cargado: {drv}")
                    driver_loaded = True
                    break
                except Exception as e:
                    print(f"âš  Driver {drv} fallÃ³: {e}")

            if not driver_loaded:
                raise Exception("No se pudo cargar ningÃºn driver de audio")

            # ---- VOLUMEN AL MÃXIMO (compat con versiones viejas) ----
            try:
                # 1) Si existiera set_gain(), usarlo
                if hasattr(self.fs, "set_gain"):
                    try:
                        self.fs.set_gain(10.0)  # 10.0 = tope de FluidSynth
                        print("ðŸ”Š Gain por set_gain=10.0")
                    except Exception:
                        pass

                # 2) Si el sintetizador expone settings internos, probar setear synth.gain
                st = getattr(self.fs, "settings", None)
                if st:
                    try:
                        # algunas versiones aceptan interfaz tipo dict
                        st["synth.gain"] = 10.0
                        print("ðŸ”Š Gain por settings['synth.gain']=10.0")
                    except Exception:
                        try:
                            # otras requieren .setnum()
                            st.setnum("synth.gain", 10.0)
                            print("ðŸ”Š Gain por settings.setnum('synth.gain',10.0)")
                        except Exception:
                            pass

                # 3) SIEMPRE: asegurar volumen/expresiÃ³n MIDI al tope
                for ch in range(16):
                    try:
                        self.fs.cc(ch, 7, 127)  # CC7 Volume
                        self.fs.cc(ch, 11, 127)  # CC11 Expression
                    except Exception:
                        pass

                self.set_reverb_send(self.reverb_send, remember=False)

            except Exception as _e:
                print("âš  No se pudo forzar gain por API; quedan CC7/CC11 a 127.")

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
            print("âœ… SoundFont cargado correctamente")
            with self.lock:
                self._apply_master_gain_locked()

            self.ok.set()

        except Exception as e:
            self.error = str(e)
            print(f"âŒ Error en setup de audio: {e}")

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
                print(f"âš  Error en render: {e}")

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
            if msg.type == "control_change":  # â† NUEVO
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
            print(f"âš  Error disparando nota: {e}")


# ------------------------------------------------------------------
# 5 Â· GUI principal
# ------------------------------------------------------------------
class DrumPadController(QWidget):
    def __init__(self, sf2_path: Path, parent=None):
        super().__init__(parent)

        print("ðŸŽ› Inicializando controlador...")

        try:
            self.audio = SoundEngine(sf2_path)
        except Exception as e:
            QMessageBox.critical(None, "Error de Audio",
                                 f"No se pudo inicializar el motor de audio:\n{e}")
            sys.exit(1)

        # Arduino
        self.arduino = self._abrir_arduino()
        # MIDI passthrough configurable (default ON para reaprovechar golpes USB-MIDI)
        val = os.environ.get('TIMBAL_MIDI_PASSTHROUGH', '1')
        self.midi_passthrough = str(val).strip().lower() not in ('0', 'false', 'off', '')
        # MIDI
        self.midi_in = self._abrir_midi()
        # GUI
        self.config_activa = 0
        # buffers de E/S
        self._rxbuf = b""
        self.midi_poll = None
        # notas activas por pad (para mute por canal)
        self.active_notes = [set() for _ in range(5)]
        self.min_velocity = 8
        self.hw_pad_notes = []
        self.hw_note_to_pad = {}
        self._build_ui()
        self._init_hw_map()
        self._timer_vu()
    # --- detecta puertos ---------------------------------------------------
    def _abrir_arduino(self):
        try:
            import serial as _serial
        except Exception:
            print("⚠ pyserial no está disponible (serial.Serial). Instalar: pip install pyserial")
            return None
        if not hasattr(_serial, 'Serial'):
            print("⚠ pyserial no está disponible (serial.Serial). Instalar: pip install pyserial")
            return None
        for p in serial.tools.list_ports.comports():
            print(f"   Puerto encontrado: {p.device} - {p.description}")
            if "Arduino Leonardo" in p.description:
            
                try:
                    arduino = _serial.Serial(p.device, 9600, timeout=0)
                    print(f"✅ Arduino conectado: {p.device}")
                    return arduino
                except Exception as e:
                    print(f"⚠ Error conectando Arduino: {e}")
        return None
    def _abrir_midi(self):
        if not getattr(self, 'midi_passthrough', False):
            print('🎹 MIDI passthrough desactivado — usando solo golpes vía serial.')
            self.midi_poll = None
            return None
        print('🎹 Buscando puertos MIDI...')
        try:
            inputs = mido.get_input_names()
            print(f'   Puertos MIDI disponibles: {inputs}')
            arduino_port = next((i for i in inputs if 'Arduino' in i), None)
            arduino_port = next((i for i in inputs if 'Arduino' in i), None) or (inputs[0] if inputs else None)
            if arduino_port:
                try:
                    midi_in = mido.open_input(arduino_port)  # sin callback → polling
                    self.midi_poll = midi_in
                    print(f'✅ Puerto MIDI conectado (poll): {arduino_port}')
                    return midi_in
                except Exception as e:
                    print(f'⚠ Error abriendo MIDI en modo polling: {e}')
                    try:
                        midi_in = mido.open_input(arduino_port, callback=self.audio.disparar)
                        print(f'✅ Puerto MIDI conectado (callback): {arduino_port}')
                        return midi_in
                    except Exception as e2:
                        print(f'⚠ Error configurando MIDI: {e2}')
                        return None
            else:
                print('⚠ No hay puertos MIDI disponibles')
                return None
        except Exception as e:
            print(f'⚠ Error listando MIDI: {e}')
            return None

    def _build_ui(self):
        self.setWindowTitle("Control de Timbal Digital")
        self.setStyleSheet("background:#2C3E50;color:#FFF;")
        main = QHBoxLayout(self)
        flechas = QVBoxLayout()
        for s, f in (("â–²", self.arriba), ("â–¼", self.abajo)):
            b = QPushButton(s);
            b.setFixedSize(40, 100);
            b.clicked.connect(f)
            flechas.addWidget(b)
        main.addLayout(flechas)

        central = QVBoxLayout()
        rej = QGridLayout()
        self.vus = [Vu() for _ in range(5)]
        for i, vu in enumerate(self.vus): rej.addWidget(vu, 0, i + 1)

        self.labels = [];
        self.botones = []
        notas_def = [
            ["A2", "E3", "A3", "C4", "E4"],
            ["E2", "B2", "E3", "G#3", "B3"],
            ["D2", "A2", "D3", "F#3", "A3"],
            ["C2", "G2", "C3", "E3", "G3"],
            ["G2", "D3", "G3", "B3", "D4"],
        ]
        for fila in range(5):
            lbl = QLabel("", alignment=Qt.AlignCenter)
            rej.addWidget(lbl, 1, fila + 1);
            self.labels.append(lbl)
            fila_b = []
            for col in range(5):
                b = QPushButton(notas_def[fila][col])
                b.clicked.connect(self._cambiar);
                fila_b.append(b)
                rej.addWidget(b, fila + 2, col + 1)
            self.botones.append(fila_b)

        # BotÃ³n para cambiar SF2 en vivo
        # BotÃ³n para cambiar SF2 â€” pendiente de implementaciÃ³n en vivo

        # Panel de controles: Reverb + Brillo (CC74) + Cambiar SF2
        controls = QVBoxLayout()

        # Reverb ON/OFF
        from PyQt5.QtWidgets import QCheckBox
        self.chk_rev_on = QCheckBox("Reverb ON")
        self.chk_rev_on.setChecked(True)
        def _toggle_reverb(state):
            self.audio.set_reverb_active(bool(state))
            self.lbl_rev_level.setText(f"Reverb level: {self.audio.reverb_level:.2f} (send: {self.audio.reverb_send:.2f})")
        self.chk_rev_on.stateChanged.connect(_toggle_reverb)
        controls.addWidget(self.chk_rev_on)
        self.lbl_rev_level = QLabel(f"Reverb level: {self.audio.reverb_level:.2f} (send: {self.audio.reverb_send:.2f})")
        self.sld_rev_level = QSlider(Qt.Horizontal)
        self.sld_rev_level.setRange(0, 100)
        self.sld_rev_level.setValue(int(self.audio.reverb_level * 100))
        # Unificar: setea level y ON/OFF según valor
        def _apply_reverb_level(v):
            level = max(0.0, min(1.0, v / 100.0))
            self.audio.set_reverb(level=level)
            send = min(1.0, max(0.0, v / 60.0))
            self.audio.set_reverb_send(send)
            self.audio.set_reverb_active(v > 0)
            self.lbl_rev_level.setText(f"Reverb level: {self.audio.reverb_level:.2f} (send: {self.audio.reverb_send:.2f})")
        self.sld_rev_level.valueChanged.connect(_apply_reverb_level)
        _apply_reverb_level(self.sld_rev_level.value())
        controls.addWidget(self.sld_rev_level)

        self.lbl_rev_room = QLabel(f"Reverb room: {self.audio.reverb_roomsize:.2f}")
        self.sld_rev_room = QSlider(Qt.Horizontal)
        self.sld_rev_room.setRange(0, 100)
        self.sld_rev_room.setValue(int(self.audio.reverb_roomsize * 100))
        self.sld_rev_room.valueChanged.connect(lambda v: (self.audio.set_reverb(roomsize=v/100.0), self.lbl_rev_room.setText(f"Reverb room: {self.audio.reverb_roomsize:.2f}")))
        controls.addWidget(self.lbl_rev_room)
        controls.addWidget(self.sld_rev_room)

        # Reverb damping (absorción de agudos en la reverb)
        self.lbl_rev_damp = QLabel(f"Reverb damp: {self.audio.reverb_damping:.2f}")
        self.sld_rev_damp = QSlider(Qt.Horizontal)
        self.sld_rev_damp.setRange(0, 100)
        self.sld_rev_damp.setValue(int(self.audio.reverb_damping * 100))
        self.sld_rev_damp.valueChanged.connect(lambda v: (self.audio.set_reverb(damping=v/100.0), self.lbl_rev_damp.setText(f"Reverb damp: {self.audio.reverb_damping:.2f}")))
        controls.addWidget(self.lbl_rev_damp)
        controls.addWidget(self.sld_rev_damp)

        self.lbl_bright = QLabel("Brillo (CC74 filtro): 100")
        self.sld_bright = QSlider(Qt.Horizontal)
        self.sld_bright.setRange(0, 127)
        self.sld_bright.setValue(100)
        def _apply_brightness(v):
            try:
                for ch in range(16):
                    self.audio.fs.cc(ch, 74, int(v))
            except Exception:
                pass
            self.lbl_bright.setText(f"Brillo (CC74): {int(v)}")
        self.sld_bright.valueChanged.connect(_apply_brightness)
        controls.addWidget(self.lbl_bright)
        controls.addWidget(self.sld_bright)

        # Boost (ganancia de velocidad)
        self.lbl_boost = QLabel(f"Boost (vel x): {getattr(self.audio, 'velocity_gain', 3.0):.2f}")
        self.sld_boost = QSlider(Qt.Horizontal)
        self.sld_boost.setRange(50, 1200)  # 0.5x .. 12.0x
        self.sld_boost.setValue(int(getattr(self.audio, 'velocity_gain', 3.0) * 100))
        def _apply_boost(v):
            try:
                self.audio.velocity_gain = max(0.5, min(12.0, v/100.0))
            except Exception:
                pass
            self.lbl_boost.setText(f"Boost (vel x): {self.audio.velocity_gain:.2f}")
        self.sld_boost.valueChanged.connect(_apply_boost)
        controls.addWidget(self.lbl_boost)
        controls.addWidget(self.sld_boost)

        self.lbl_master = QLabel(f"Master boost (dB): {self.audio.master_db:+.1f}")
        self.sld_master = QSlider(Qt.Horizontal)
        self.sld_master.setRange(-600, int(self.audio.max_master_db * 10))
        self.sld_master.setValue(int(self.audio.master_db * 10))
        def _apply_master(v):
            db = v / 10.0
            self.audio.set_master_gain_db(db)
            self.lbl_master.setText(f"Master boost (dB): {self.audio.master_db:+.1f}")
        self.sld_master.valueChanged.connect(_apply_master)
        controls.addWidget(self.lbl_master)
        controls.addWidget(self.sld_master)

        self.chk_limiter = QCheckBox("Limitador ON")
        self.chk_limiter.setChecked(self.audio.limiter_enabled)
        self.chk_limiter.stateChanged.connect(lambda state: self.audio.set_limiter_enabled(bool(state)))
        controls.addWidget(self.chk_limiter)


        self.lbl_gate = QLabel(f"Filtro golpes leves: {self.min_velocity}")
        self.sld_gate = QSlider(Qt.Horizontal)
        self.sld_gate.setRange(0, 40)
        self.sld_gate.setValue(self.min_velocity)
        def _apply_gate(v):
            self.min_velocity = max(0, int(v))
            self.lbl_gate.setText(f"Filtro golpes leves: {self.min_velocity}")
        self.sld_gate.valueChanged.connect(_apply_gate)
        controls.addWidget(self.lbl_gate)
        controls.addWidget(self.sld_gate)

        # Presets de reverb
        btn_preset_seco = QPushButton("Preset: Seco")
        btn_preset_seco.clicked.connect(lambda: self._preset_reverb('seco'))
        controls.addWidget(btn_preset_seco)

        btn_preset_media = QPushButton("Preset: Media")
        btn_preset_media.clicked.connect(lambda: self._preset_reverb('media'))
        controls.addWidget(btn_preset_media)

        btn_preset_sala = QPushButton("Preset: Sala")
        btn_preset_sala.clicked.connect(lambda: self._preset_reverb('sala'))
        controls.addWidget(btn_preset_sala)

        btn_sf2 = QPushButton("Cambiar SF2")
        btn_sf2.clicked.connect(self._cambiar_sf2)
        controls.addWidget(btn_sf2)

        btn_test = QPushButton("Probar sonido")
        btn_test.clicked.connect(self._test_sound)
        controls.addWidget(btn_test)


        # Reconectar I/O
        btn_reco = QPushButton("Reconectar I/O")
        btn_reco.clicked.connect(self._reconectar_io)
        controls.addWidget(btn_reco)
        central.addLayout(controls)

        self._colores();
        self._etiquetas()
        central.addLayout(rej);
        main.addLayout(central)

    # --- lÃ³gica ------------------------------------------------------------
    def _init_hw_map(self):
        try:
            base_row = self.botones[0] if self.botones else []
            notes = []
            mapping = {}
            for idx, btn in enumerate(base_row):
                note = self._to_midi(btn.text())
                notes.append(note)
                if note not in mapping:
                    mapping[note] = idx
            self.hw_pad_notes = notes
            self.hw_note_to_pad = mapping
            if mapping:
                print(f"HW pad map inicial: {mapping}")
        except Exception as e:
            self.hw_pad_notes = []
            self.hw_note_to_pad = {}
            print(f"No se pudo crear mapa HW: {e}")

    def _note_for_pad(self, pad_idx: int) -> int:
        fila = self.botones[self.config_activa] if 0 <= self.config_activa < len(self.botones) else []
        if 0 <= pad_idx < len(fila):
            return self._to_midi(fila[pad_idx].text())
        raise IndexError('Pad fuera de rango')

    def _map_midi_message(self, msg: Message) -> Message:
        if not getattr(self, 'hw_note_to_pad', None):
            return msg
        if msg.type in ('note_on', 'note_off'):
            pad_idx = self.hw_note_to_pad.get(getattr(msg, 'note', -1))
            if pad_idx is None:
                return msg
            try:
                target_note = self._note_for_pad(pad_idx)
            except Exception:
                return msg
            new_msg = msg.copy(note=target_note)
            if msg.type == 'note_on' and getattr(msg, 'velocity', 0) and pad_idx < len(self.vus):
                try:
                    self.vus[pad_idx].actualizar(int(msg.velocity))
                except Exception:
                    pass
            return new_msg
        return msg

    def _cambiar(self):
        btn = self.sender()
        fila, col = [(r, c) for r, f in enumerate(self.botones)
                     for c, b in enumerate(f) if b is btn][0]
        dlg = NoteSelectorDialog(self)
        if dlg.exec_():
            nota = dlg.nota();
            btn.setText(nota)
            if fila == self.config_activa: self._enviar_nota(nota, col)
            self._etiquetas()

    def _enviar_nota(self, nota, col):
        if self.arduino and self.arduino.is_open:
            try:
                midi = self._to_midi(nota)
                data = json.dumps({"note": midi, "col": col}) + "\n"
                self.arduino.write(data.encode())
            except Exception as e:
                print(f"âš  Error enviando nota: {e}")

    @staticmethod
    def _to_midi(n):
        nombres = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        return nombres.index(n[:-1]) + 12 * (int(n[-1]) + 1)

    def arriba(self):
        self._cfg(-1)

    def abajo(self):
        self._cfg(+1)

    def _cfg(self, d):
        self.config_activa = (self.config_activa + d) % 5
        self._colores();
        self._etiquetas()
        if self.arduino and self.arduino.is_open:
            try:
                notas = [self._to_midi(b.text()) for b in self.botones[self.config_activa]]
                data = json.dumps({"notes": notas}) + "\n"
                self.arduino.write(data.encode())
            except Exception as e:
                print(f"âš  Error enviando configuraciÃ³n: {e}")

    def _colores(self):
        for i, f in enumerate(self.botones):
            for b in f:
                st = ("background:#3498DB;color:#FFF;border:2px solid #2980B9;"
                      if i == self.config_activa else
                      "background:#ECF0F1;color:#2980B9;border:2px solid #2980B9;")
                b.setStyleSheet(st)

    def _etiquetas(self):
        for i, l in enumerate(self.labels):
            l.setText(self.botones[self.config_activa][i].text())


    def _trigger_pad(self, pad_idx: int, velocity: int, *, note: int = None, auto_off_ms: int = None, send_audio: bool = True):
        vel = int(max(1, min(127, velocity)))
        if 0 <= pad_idx < len(self.vus):
            try:
                self.vus[pad_idx].actualizar(vel)
            except Exception:
                pass
        note_value = note
        if note_value is None:
            try:
                note_value = self._note_for_pad(pad_idx)
            except Exception:
                note_value = None
        if not send_audio or note_value is None:
            return
        try:
            self.audio.disparar(Message('note_on', note=note_value, velocity=vel, channel=0))
            if auto_off_ms:
                QTimer.singleShot(int(max(1, auto_off_ms)),
                                   lambda n=note_value: self.audio.disparar(Message('note_off', note=n, velocity=0, channel=0)))
        except Exception as e:
            print(f'[WARN] Trigger pad audio: {e}')

    def _test_sound(self):
        try:
            note = self._note_for_pad(0)
        except Exception:
            note = 48
        try:
            self._trigger_pad(0, 110, note=note, auto_off_ms=250, send_audio=True)
        except Exception as e:
            print('Test sonido:', e)

    def _cambiar_sf2(self):
        fn, _ = QFileDialog.getOpenFileName(self, 'Seleccionar SoundFont', '.', 'SoundFont (*.sf2)')
        if not fn:
            return
        try:
            self.audio.load_sf2_live(Path(fn))
            cfg = load_config(); cfg['last_sf2'] = fn; save_config(cfg)
            QMessageBox.information(self, 'SoundFont', 'SoundFont cargado correctamente.')
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'No se pudo cambiar el SoundFont:\n{e}')

    def _reconectar_io(self):
        try:
            if self.arduino and self.arduino.is_open: self.arduino.close()
        except Exception: pass
        try:
            if getattr(self, 'midi_poll', None) is not None:
                self.midi_poll.close(); self.midi_poll = None
        except Exception: pass
        try:
            if getattr(self, 'midi_in', None) is not None:
                self.midi_in.close(); self.midi_in = None
        except Exception: pass
        self.arduino = self._abrir_arduino()
        self.midi_in = self._abrir_midi()

    def _preset_reverb(self, preset: str):
        p = (preset or '').lower()
        if p == 'seco':
            self.audio.set_reverb_active(False)
            self.sld_rev_level.setValue(0)
        elif p == 'media':
            self.audio.set_reverb_active(True)
            self.audio.set_reverb(roomsize=0.45, level=0.25, damping=0.25)
            self.sld_rev_room.setValue(45); self.sld_rev_level.setValue(25); self.sld_rev_damp.setValue(25)
        elif p == 'sala':
            self.audio.set_reverb_active(True)
            self.audio.set_reverb(roomsize=0.70, level=0.40, damping=0.20)
            self.sld_rev_room.setValue(70); self.sld_rev_level.setValue(40); self.sld_rev_damp.setValue(20)

    def _timer_vu(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._leer_serial)
        self.timer.start(50)

    def _leer_serial(self):
        # Drenar bytes
        if self.arduino:
            try:
                n = self.arduino.in_waiting
                if n:
                    self._rxbuf += self.arduino.read(n)
            except Exception:
                pass
        # Procesar líneas
        if getattr(self, '_rxbuf', None):
            parts = self._rxbuf.split(b'\n')
            self._rxbuf = parts[-1]
            for raw in parts[:-1][:20]:
                line = raw.decode(errors='ignore').strip()
                if not line: continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                keys = ['A0','A1','A2','A3']
                if all(k in d for k in keys):
                    for i,k in enumerate(keys):
                        if i < len(self.vus):
                            val = int(d.get(k, 0))
                            self.vus[i].actualizar(val // 8)
                if isinstance(d, dict) and 'HIT' in d:
                    try:
                        hit = d.get('HIT', {})
                        pad_idx = int(hit.get('ch', 0))
                        vel = int(hit.get('vel', 0))
                        if vel <= 0:
                            continue
                        min_vel = max(0, int(getattr(self, 'min_velocity', 0)))
                        if vel < min_vel:
                            continue
                        note_value = None
                        if 'note' in hit:
                            try:
                                note_value = int(hit['note'])
                            except Exception:
                                note_value = None
                        send_audio = not self.midi_passthrough
                        auto_off = 220 if send_audio else None
                        self._trigger_pad(pad_idx, vel, note=note_value, auto_off_ms=auto_off, send_audio=send_audio)
                    except Exception as e:
                        print(f"[WARN] Procesando HIT: {e}")
                        continue
                if isinstance(d, dict) and 'MUTE' in d:
                    try:
                        m = d.get('MUTE', {})
                        ch = int(m.get('ch', 0)); state = int(m.get('state', 0))
                        if 0 <= ch < len(self.botones[self.config_activa]) and state == 1:
                            try:
                                self.vus[ch].actualizar(0)
                            except Exception:
                                pass
                            nota_txt = self.botones[self.config_activa][ch].text()
                            note = self._to_midi(nota_txt)
                            self.audio.disparar(Message('note_off', note=note, velocity=0, channel=0))
                    except Exception:
                        pass
        # Poll MIDI
        try:
            if self.midi_poll is not None:
                for msg in self.midi_poll.iter_pending():
                    mapped = self._map_midi_message(msg)
                    self.audio.disparar(mapped)
        except Exception:
            pass

# ------------------------------------------------------------------
# 6 · lanzador
# ------------------------------------------------------------------
def main():
    print("Iniciando Timbal Digital...")

    app = QApplication(sys.argv)

    pal = QPalette()
    pal.setColor(QPalette.Window, QColor("#4E342E"))
    pal.setColor(QPalette.WindowText, Qt.white)
    pal.setColor(QPalette.Button, QColor("#8D6E63"))
    pal.setColor(QPalette.ButtonText, Qt.white)
    pal.setColor(QPalette.Highlight, QColor("#A1887F"))
    pal.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(pal)

    cfg = {}
    try:
        cfg = load_config()
    except Exception:
        cfg = {}
    last_sf2 = cfg.get('last_sf2')
    if last_sf2 and Path(last_sf2).exists():
        sf2 = last_sf2
    else:
        sf2, _ = QFileDialog.getOpenFileName(None, 'Seleccionar SoundFont', '.', 'SoundFont (*.sf2)')
        if not sf2:
            QMessageBox.critical(None, 'Error', 'No seleccionaste ningún SoundFont.')
            sys.exit(1)
        cfg['last_sf2'] = sf2
        save_config(cfg)

    try:
        w = DrumPadController(sf2_path=Path(sf2))
        w.resize(900, 460)
        w.show()
        print("Aplicación iniciada correctamente")
        sys.exit(app.exec_())
    except Exception as e:
        QMessageBox.critical(None, 'Error Fatal', f'Error iniciando la aplicación:\n{e}')
        print(f"Error fatal: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

