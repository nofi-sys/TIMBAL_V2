# Backlog operativo por archivo y modulo

## Regla de trabajo
En esta fase se construye sobre la infraestructura actual. Todo lo que exija hardware nuevo, recableado o una plataforma aparte queda fuera del backlog inmediato.

## Baseline que no hay que deformar

### `C:\MUSICA\TIMBAL_V2\app\ui\main_window.py`
Rol:
UI operativa principal.

Instruccion:
- mantenerla estable
- como maximo, agregar un acceso al laboratorio si despues hiciera falta

### `C:\MUSICA\TIMBAL_V2\app\ui\pages\pads.py`
Rol:
flujo de pads para uso normal.

Instruccion:
- no meter logging crudo
- no meter replay
- no meter evaluacion de modelos

### `C:\MUSICA\TIMBAL_V2\app\io\timbal_input.py`
Rol:
router operativo de MIDI/serial/configuracion.

Instruccion:
- conservarlo para operacion
- no usarlo como transporte de muestras crudas
- no cargarlo con obligaciones del laboratorio

### `C:\MUSICA\TIMBAL_V2\arduino\TIMBAL_RUNTIME_PRESENCE_V1.ino`
Rol:
firmware operativo de presencia/calibracion/hits.

Instruccion:
- congelarlo como baseline
- no convertirlo en firmware de investigacion

## Archivos a crear o modificar ahora

### `C:\MUSICA\TIMBAL_V2\main.py`
Accion:
agregar `--run-timbal-lab`.

Objetivo:
abrir el laboratorio sin contaminar el flujo principal.

### Nueva carpeta `C:\MUSICA\TIMBAL_V2\app\timbal_lab\`
Objetivo:
contener todo el trabajo experimental inmediato usando la infraestructura actual.

Submodulos minimos:
- `sources/`
- `logging/`
- `profiles/`
- `features/`
- `models/`
- `render/`
- `ui/`
- `eval/`

### `app\timbal_lab\ui\window.py`
Objetivo:
ventana principal del laboratorio.

Debe incluir:
- inicio y fin de sesion
- seleccion de fuente
- estado de captura
- toggle de muteo por software
- panel basico de hits
- accion de replay

### `app\timbal_lab\sources\analog_raw_source.py`
Objetivo:
envolver el experimento host-side analogico actual como fuente reutilizable.

Instruccion:
- reutilizar la logica valida de `app/host_analog/stream.py`
- no reescribirla desde cero

### `app\timbal_lab\sources\replay_source.py`
Objetivo:
reproducir sesiones grabadas como si fueran live.

### `app\timbal_lab\logging\session_recorder.py`
Objetivo:
guardar sesiones completas.

Debe escribir:
- `manifest.json`
- `arduino_raw.bin`
- `events.jsonl`

### `app\timbal_lab\profiles\patch_profile.py`
Objetivo:
definir y persistir perfiles por parche.

Debe incluir al menos:
- `patch_id`
- afinacion
- thresholds sugeridos
- refractory
- parametros temporales
- curvas iniciales del modelo

### `app\timbal_lab\features\onset_features.py`
Objetivo:
extraer features basicas sobre la infraestructura actual.

Minimo:
- peak
- initial_slope
- area_5ms
- area_15ms
- time_to_peak
- tail_ratio
- ioi_prev
- pre_hit_energy

### `app\timbal_lab\models\legacy_map.py`
Objetivo:
capturar el comportamiento actual para compararlo, no para mejorarlo.

### `app\timbal_lab\models\state_map_v1.py`
Objetivo:
primer modelo interpretable orientado a continuidad y memoria temporal.

### `app\timbal_lab\eval\model_bench.py`
Objetivo:
comparar `legacy_map` vs `state_map_v1` sobre el mismo dataset.

Debe medir:
- monotonicidad dinamica
- continuidad
- repetibilidad
- comportamiento del muteo

### `app\timbal_lab\render\renderer_adapter.py`
Objetivo:
usar el engine actual como renderer de prueba sin tocar la app principal.

## Archivos a reutilizar tal como estan, por ahora

### `C:\MUSICA\TIMBAL_V2\app\host_analog\stream.py`
Uso:
fuente de referencia para parseo binario y timestamps.

### `C:\MUSICA\TIMBAL_V2\app\host_analog\window.py`
Uso:
referencia de UI, no destino de crecimiento futuro.

### `C:\MUSICA\TIMBAL_V2\app\runtime.py`
Uso:
bootstrap de Qt y audio.

## Firmware inmediato

### `C:\MUSICA\TIMBAL_V2\arduino\HOST_ANALOG_STREAM_EXPERIMENT.ino`
Decision:
usar este sketch como base inmediata.

Instruccion:
- no bloquear el sprint esperando una version nueva multicanal
- primero capturar bien con lo que ya existe

## Firmware posterior, solo si hace falta

### Futuro opcional: `C:\MUSICA\TIMBAL_V2\arduino\HOST_ANALOG_STREAM_V2_MULTICHANNEL.ino`
Condicion:
crear este sketch solo despues de demostrar con datos que la infraestructura actual ya quedo exprimida.

## Orden de implementacion inmediato

### Orden 1
`main.py` + `app/timbal_lab/` + ventana minima.

### Orden 2
`AnalogRawSource` + `SessionRecorder`.

### Orden 3
`ReplaySource` + `PatchProfile`.

### Orden 4
extractor de features + `ModelBench`.

### Orden 5
`state_map_v1` + `RendererAdapter`.

## Lo que queda explicitamente fuera de esta fase
- separar piezos por canal
- comprar sensores
- comprar placas nuevas
- crear una estructura `shared/` o `core/`
- meter machine learning
