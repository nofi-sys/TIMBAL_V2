# Build de `timbal.exe` en Windows 11

## Requisitos
- Python 3.11/3.12 de 64 bits y `pip`.
- Ambiente virtual activo.
- Drivers de audio estándar de Windows (WASAPI/DirectSound) y permisos para crear puertos MIDI virtuales.

## Instalación de dependencias
```powershell
pip install -r requirements-build.txt
```
`requirements.txt` cubre runtime (PyQt5, mido/rtmidi, pyserial, pyFluidSynth, pygame) y `requirements-build.txt` agrega PyInstaller.

## Empaquetado con PyInstaller
```powershell
pyinstaller --noconfirm --clean build_exe.spec
```
- Salida: `dist/timbal/` (mantener carpeta completa, no solo el `.exe`).
- El spec ya incluye:
  - `fluidsynth_dlls/*.dll` para que pyFluidSynth encuentre sus dependencias.
  - `soundonts/*.sf2` con el SoundFont `timpani_collections.sf2` como default.
  - Hidden imports (`mido.backends.rtmidi`, `serial.tools.list_ports`, `rhythm_dino_game`) para evitar módulos faltantes.
- El ejecutable acepta:
  - `--legacy-ui` / `--new-ui` (default) para elegir interfaz.
  - `--run-dino` (interno, lo usa la UI para abrir el minijuego sin requerir archivos sueltos).

## Verificación rápida post-build
- Ejecutar `dist/timbal/timbal.exe` y comprobar que:
  - Carga el SoundFont sin pedir archivo (usa el incluido) y suena un pad.
  - El menú Juegos abre DINO_RITMO y responde a golpes/teclas.
  - La carpeta `fluidsynth_dlls` está junto al `.exe`; si falta audio, revisar que antivirus no bloquee DLLs.
- Para mover a otra PC, copiar completa la carpeta `dist/timbal` (o comprimirla).
