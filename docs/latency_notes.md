# Notas de latencia

## Diagnostico confirmado
En esta maquina, `mido.get_input_names()` devuelve:
- `Digital Piano 0`
- `Arduino Leonardo 1`

La app anterior intentaba abrir un puerto MIDI virtual. En Windows eso falla con `NotImplementedError`, y luego hacia fallback a `inputs[0]`.

Consecuencia:
- REAPER podia usar `Arduino Leonardo 1` directo.
- La app propia podia quedar oyendo `Digital Piano 0` o depender del camino serial JSON.

## Fuentes probables de latencia que si existian en la app
1. Seleccion incorrecta del input MIDI.
2. Polling serial con `QTimer` cada `15 ms`.
3. Serial en `9600` para eventos de golpe.
4. Buffers por defecto de FluidSynth mas holgados que un host tipo REAPER.

## Cambios aplicados
- Nuevo router compartido en `app/io/timbal_input.py`.
- Prioridad explicita a nombres tipo Arduino/Leonardo/Timbal.
- Thread dedicado para serial.
- La app principal quedo en modo `serial-first` para golpes, porque el serial trae `pad_idx` y alimenta el VU.
- MIDI sigue abierto y priorizado para deteccion de dispositivo, pero no manda los `HIT` principales de la ventana de pads.
- Bootstrap de audio con:
  - `TIMBAL_FS_SAMPLE_RATE=48000`
  - `TIMBAL_FS_PERIOD_SIZE=64`
  - `TIMBAL_FS_PERIODS=2`

## Que falta medir
- Timestamp de entrada al recibir el golpe.
- Timestamp al disparar `note_on` en el engine.
- Prueba A/B entre:
  - MIDI fisico
  - serial JSON
  - mismo patron en REAPER

## Hipotesis vigente
La mayor diferencia percibida venia del lado de input, no solo del render de audio.
