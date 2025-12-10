# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

block_cipher = None

project_root = Path(__file__).parent.resolve()

datas = []

dll_dir = project_root / "fluidsynth_dlls"
if dll_dir.exists():
    for dll in dll_dir.glob("*.dll"):
        datas.append((dll, "fluidsynth_dlls"))

sf2_dir = project_root / "soundonts"
if sf2_dir.exists():
    for sf2 in sf2_dir.glob("*.sf2"):
        datas.append((sf2, "soundonts"))

hiddenimports = [
    "mido.backends.rtmidi",
    "serial",
    "serial.tools.list_ports",
    "rhythm_dino_game",
    "pygame",
]

a = Analysis(
    ['main.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=[(str(src), dest) for src, dest in datas],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='timbal',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    icon=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='timbal',
)
