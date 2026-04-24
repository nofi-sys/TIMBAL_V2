# TIMBAL_V2 Agent Context

## Estado actual
- La app principal corre por `main.py --new-ui`.
- El entrenador ritmico base corre por `main.py --run-trainer`.
- El experimento de analogico host-side corre por `main.py --run-host-analog`.
- El launcher de desarrollo rapido es `run_timbal.bat`.
- El launcher de flasheo Arduino es `flash_arduino.bat` / `flash_arduino.ps1`.

## Arquitectura de input
- Todo consumo de dispositivo debe pasar por `app/io/timbal_input.py`.
- La app principal usa el router en modo `serial-first` para `HIT`, porque el serial trae `pad_idx` y permite VU por parche.
- MIDI queda abierto como respaldo y para mensajes auxiliares.
- Hay deduplicacion corta entre MIDI y serial para evitar doble disparo si el firmware emite por ambos.

## Hallazgo de hardware importante
- Con el firmware actual la GUI solo recibe eventos `HIT` y `MUTE`.
- La GUI no recibe nivel analogico continuo ni un indicador real de "cable conectado".
- Por eso la deteccion de jack/cable conectado no se puede resolver de forma confiable solo desde la PC.
- La mitigacion actual en software es `pad_enabled`: cada pad se puede prender o apagar manualmente desde la GUI.

## Cambio de GUI aplicado
- `app/ui/pages/pads.py` ahora muestra un toggle por pad con icono de encendido.
- Estado persistente: `pad_enabled` en la config JSON.
- La GUI ahora tambien muestra estado de presencia por pad (`Estable`, `Flotante`, `Sin datos`).
- Hay acciones rapidas `Todos ON`, `Todos OFF` y `Solo estables`.
- Default actual: si no existe config previa, todos los pads arrancan manualmente habilitados.
- Hay ventana nueva de `Calibracion en vivo` desde `Configuracion > Calibracion en vivo...`.
- Hay seleccion manual de `bank/preset` del SoundFont desde `Configuracion > Preset/Bank SoundFont...`.
- La calibracion en vivo permite:
  - leer `CFGSTATE` del firmware
  - ajustar `min_hit`, `quiet`, `presence_noise`, `refractory`, `keep_connected`
  - persistir esos valores en `config.json`
- Un pad apagado:
  - no acepta clicks manuales
  - ignora `HIT` externos
  - apaga su VU
  - fuerza `note_off` al desactivarse
- Un pad con estado `Flotante` tambien queda bloqueado aunque este manualmente en ON.

## Tooling Arduino instalado
- Arduino IDE 2.3.8 instalado en:
  - `C:\Users\Oliverio\AppData\Local\Programs\Arduino IDE`
- `arduino-cli.exe` usable desde:
  - `C:\Users\Oliverio\AppData\Local\Programs\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe`
- Core instalado:
  - `arduino:avr`
- Libreria instalada:
  - `ArduinoJson`
- Board detectado en esta maquina:
  - `COM3`
  - `arduino:avr:leonardo`

## Flujo de flasheo por terminal
- `flash_arduino.bat`
- Ejemplos:
  - `flash_arduino.bat -CompileOnly`
  - `flash_arduino.bat -Sketch .\arduino\HOST_ANALOG_STREAM_EXPERIMENT.ino`
  - `flash_arduino.bat -Sketch .\arduino\HOST_ANALOG_STREAM_EXPERIMENT.ino -Port COM3`
- El script detecta `Leonardo` automaticamente cuando puede.
- Si recibe un `.ino` suelto, lo copia a una carpeta temporal con el nombre correcto para que `arduino-cli` pueda compilarlo.

## Firmware recomendado actual
- Sketch nuevo:
  - `arduino/TIMBAL_RUNTIME_PRESENCE_V1.ino`
- Protocolo serial nuevo:
  - `{"HIT":{"ch":0,"vel":97}}`
  - `{"PADSTATE":{"ch":0,"conn":1,"noise":4,"value":12,"peak":51}}`
  - `{"REQ":"CFG"}`
  - `{"CFG":{"min_hit":24,"quiet":28,"presence_noise":16,"refractory":38,"keep_connected":900}}`
  - `{"CFGSTATE":{"min_hit":24,"quiet":28,"presence_noise":16,"refractory":38,"keep_connected":900}}`
- Baud esperado por la app:
  - `115200`
- Objetivo:
  - bloquear entradas flotantes por firmware
  - reportar presencia/estabilidad por canal a la GUI
  - aceptar calibracion live sin recompilar

## Nota importante sobre SoundFonts
- El motor de audio arranca en `preset 0` si no se le dice otra cosa.
- Para bancos GM/GS generales, timbales suele vivir en `bank 0 / preset 47`.
- La UI ya permite cambiar ese `bank/preset` y lo persiste en config.

## Limitaciones actuales del repo Arduino
- `arduino/TIMBAL_GUI_GPT5_v2.ino` en este repo esta truncado y no alcanza para compilar.
- `arduino/HOST_ANALOG_STREAM_EXPERIMENT.ino` si es un sketch completo y sirve para validar el pipeline de compile/upload.

## Proximo backlog natural
- Medir latencia real por timestamp de entrada y salida de audio.
- Permitir seleccion explicita de input MIDI desde UI.
- Reemplazar JSON serial de golpes por un camino MIDI/binario mas directo en firmware.
- Si se quiere deteccion real de cable/parche conectado, agregar telemetria analogica o estado de presencia desde firmware.
- Expandir el trainer a otras subdivisiones y patrones.
