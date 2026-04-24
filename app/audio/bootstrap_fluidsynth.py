"""Bootstrap helpers for FluidSynth DLL discovery and import."""
from __future__ import annotations

import os
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Tuple

from app.paths import ensure_on_path, resource_path

DLL_DIR = resource_path('fluidsynth_dlls')
POSSIBLE_DLLS = [
    'libfluidsynth-3.dll',
    'libfluidsynth.dll',
    'fluidsynth.dll',
    'libfluidsynth-2.dll',
]
COMMON_DEPS = [
    'libglib-2.0-0.dll',
    'libgobject-2.0-0.dll',
    'libgthread-2.0-0.dll',
    'libintl-8.dll',
    'libinstpatch-2.dll',
    'sndfile.dll',
]
WINDOWS_COMPAT_DIR = Path(r'C:\tools\fluidsynth\bin')
_FLUIDSYNTH_MODULE = None


def _ensure_dll_dir() -> Path:
    dir_path = resource_path('fluidsynth_dlls')
    if not dir_path.exists():
        raise FileNotFoundError(f'Expected FluidSynth DLLs under {dir_path}')
    return dir_path


def _inject_path(dir_path: Path) -> None:
    ensure_on_path(dir_path)


def _ensure_windows_compat_dir(dir_path: Path) -> None:
    """Work around pyFluidSynth's hard-coded Windows lookup path."""
    if os.name != 'nt':
        return
    try:
        WINDOWS_COMPAT_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        return

    for name in POSSIBLE_DLLS + COMMON_DEPS:
        src = dir_path / name
        dst = WINDOWS_COMPAT_DIR / name
        if not src.exists() or dst.exists():
            continue
        try:
            shutil.copy2(src, dst)
        except OSError:
            pass


def _select_dll(dir_path: Path) -> Path:
    for name in POSSIBLE_DLLS:
        cand = dir_path / name
        if cand.exists():
            print(f'[fluidsynth] Using DLL candidate: {cand.name}')
            os.environ['PYFLUIDSYNTH_LIB'] = str(cand)
            return cand
    available = sorted(p.name for p in dir_path.glob('*.dll'))
    raise FileNotFoundError(f'No FluidSynth DLL found in {dir_path}. Available: {available}')


def _report_dependencies(dir_path: Path) -> None:
    print('[fluidsynth] Checking dependent DLLs...')
    missing = []
    for dep in COMMON_DEPS:
        if (dir_path / dep).exists():
            print(f'   OK  {dep}')
        else:
            print(f'   MISSING  {dep}')
            missing.append(dep)
    if missing:
        print('[fluidsynth] Missing dependencies: ' + ', '.join(missing))
        print('   Suggested: copy full FluidSynth release or install via conda-forge.')


@contextmanager
def _temporary_cwd(path: Path):
    original = Path.cwd()
    try:
        os.chdir(str(path))
        yield
    finally:
        os.chdir(str(original))


def _check_dll_dependencies(dll_path: Path) -> Tuple[bool, str]:
    try:
        import ctypes
        from ctypes import wintypes
    except Exception as exc:
        return False, f'ctypes unavailable: {exc}'
    try:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    except AttributeError:
        return True, 'non-Windows platform'
    kernel32.SetDllDirectoryW.argtypes = [wintypes.LPCWSTR]  # type: ignore[attr-defined]
    kernel32.SetDllDirectoryW.restype = wintypes.BOOL  # type: ignore[attr-defined]
    kernel32.SetDllDirectoryW(str(dll_path.parent))  # type: ignore[attr-defined]
    load_with_altered = 0x00000008
    handle = kernel32.LoadLibraryExW(str(dll_path), None, load_with_altered)  # type: ignore[attr-defined]
    if handle:
        kernel32.FreeLibrary(handle)  # type: ignore[attr-defined]
        return True, 'ok'
    error_code = kernel32.GetLastError()  # type: ignore[attr-defined]
    return False, f'LoadLibraryExW failed with code {error_code}'


def _try_alternative_load(dll_path: Path) -> None:
    try:
        import ctypes
    except Exception:
        return
    try:
        with _temporary_cwd(dll_path.parent):
            ctypes.CDLL(dll_path.name)
            print('[fluidsynth] Alternative ctypes load succeeded.')
    except Exception as exc:
        raise RuntimeError(f'Alternative ctypes load failed: {exc}')


def bootstrap():
    global _FLUIDSYNTH_MODULE
    if _FLUIDSYNTH_MODULE is not None:
        return _FLUIDSYNTH_MODULE

    dir_path = _ensure_dll_dir()
    _inject_path(dir_path)
    _ensure_windows_compat_dir(dir_path)
    dll_path = _select_dll(dir_path)
    _report_dependencies(dir_path)

    ok, detail = _check_dll_dependencies(dll_path)
    if not ok:
        print(f"[fluidsynth] DLL dependency check failed: {detail}")
        _try_alternative_load(dll_path)

    try:
        import fluidsynth  # type: ignore
    except ImportError as exc:
        raise ImportError('pyFluidSynth is not available. Install with "pip install pyFluidSynth".') from exc

    _FLUIDSYNTH_MODULE = fluidsynth
    print('[fluidsynth] Module imported successfully.')
    return fluidsynth
