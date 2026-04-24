# Plan consolidado de implementacion por etapas

## Criterio rector
La prioridad no es redisenar el sistema ni comprar hardware. La prioridad es sacar el mayor rendimiento posible de la infraestructura actual, medir con seriedad y recien despues decidir si existe un limite duro que justifique una etapa posterior de hardware.

## Decisiones de arquitectura

### Decision 1. Mantener la app principal estable
La UI operativa y el flujo actual siguen siendo baseline. No se mezclan desde el dia 1 con logging crudo, replay, evaluacion de modelos ni protocolos experimentales.

### Decision 2. Crear una app de laboratorio dentro del repo actual
Tomo la idea de ChatGPT Pro de separar produccion e investigacion, pero la adapto a este repo:
- no conviene abrir un paquete raiz `timbal_lab/` en esta etapa
- conviene crear `app/timbal_lab/` para reutilizar `app.runtime`, `app.audio`, `app.host_analog` y utilidades existentes sin una extraccion prematura a `shared/`

### Decision 3. No extraer `shared/` o `core/` todavia
Ese refactor solo vale la pena si la duplicacion aparece de verdad. En esta fase cuesta mas de lo que aporta.

### Decision 4. Hardware nuevo queda postergado
En la fase actual:
- no comprar sensores
- no armar un dispositivo especial
- no cambiar plataforma

La unica excepcion posible, y no inmediata, es una mejora muy menor y justificada para sincronizacion visual si realmente hiciera falta. Pero el plan base no depende de eso.

## Lo que tomo de la propuesta de ChatGPT Pro

### Mantener
- app paralela de laboratorio
- `SessionRecorder`
- `ReplaySource`
- `PatchProfileManager`
- `ModelBench`
- `RendererAdapter`
- protocolos repetibles

### Ajustar al repo
- usar `app/timbal_lab/` en vez de un paquete raiz nuevo
- reutilizar el experimento host-side analogico actual antes de escribir firmware nuevo
- dejar el sketch multicanal como etapa posterior, no como requisito del primer sprint

### Postergar
- separacion de piezos por canal
- hardware adicional
- refactor grande de paquetes compartidos
- machine learning

## Lectura concreta del estado actual

### Lo que ya tenemos y hay que explotar
- `app/host_analog/stream.py` ya lee stream binario y calcula timestamps y lag estimado.
- `app/host_analog/window.py` ya ofrece UI minima para ver onda y detectar hits en host.
- `app/runtime.py` ya resuelve bootstrap Qt y engine.
- `app/io/timbal_input.py` ya sirve para operacion y configuracion, aunque no debe convertirse en bus de telemetria cruda.
- `arduino/HOST_ANALOG_STREAM_EXPERIMENT.ino` ya permite adquirir senal cruda con la infraestructura actual.

### Lo que no hay que hacer ahora
- reescribir el runtime principal
- fusionar laboratorio y app operativa
- exigir canales separados antes de arrancar
- comprar componentes sin dataset

## Etapas

### Etapa 0. Baseline y convenciones
Objetivo:
congelar el estado actual y dejar un marco reproducible de trabajo.

Acciones:
1. documentar baseline de app, firmware, soundfont y configuracion
2. definir carpeta de sesiones y convencion de nombres
3. decidir estructura minima de `PatchProfile`
4. fijar que la fase actual usa la infraestructura tal como esta hoy

Entregables:
- baseline escrito
- convencion de sesiones
- formato inicial de perfil de parche

Criterio de cierre:
una sesion puede repetirse sabiendo exactamente que version y que parametros se usaron.

### Etapa 1. Laboratorio minimo con infraestructura actual
Objetivo:
abrir una app de laboratorio que capture y guarde sesiones sin tocar la app principal.

Acciones:
1. agregar `--run-timbal-lab` en `main.py`
2. crear `app/timbal_lab/`
3. envolver el flujo actual de host-side analogico como `AnalogRawSource`
4. crear `SessionRecorder`
5. guardar `manifest.json`, `arduino_raw.bin` y `events.jsonl`

Importante:
en esta etapa no hace falta firmware nuevo. Se usa el experimento actual como base.

Entregables:
- launcher nuevo
- sesion grabable a disco
- estructura minima de datos

Criterio de cierre:
se puede grabar una sesion de 30 a 60 segundos con la infraestructura actual y sin romper `--new-ui` ni `--run-host-analog`.

### Etapa 2. Sync, replay y perfiles de parche
Objetivo:
hacer que una sesion sirva para analisis repetible, no solo para mirar una vez.

Acciones:
1. agregar `SYNC` desde host con flash visual, click y evento logueado
2. implementar `ReplaySource`
3. crear `PatchProfileManager`
4. guardar metadata de parche, afinacion y notas del experimento
5. agregar un toggle de muteo por software dentro del laboratorio

Entregables:
- replay offline
- perfiles por parche en JSON o YAML
- sesion sincronizable

Criterio de cierre:
una misma sesion puede reproducirse varias veces y compararse con distintos modelos o configuraciones.

### Etapa 3. Features y observabilidad con lo que ya existe
Objetivo:
medir hasta donde llega honestamente la infraestructura actual.

Acciones:
1. implementar extractor de features basicas
2. ejecutar un protocolo corto con pocas posiciones y dinamicas
3. generar tabla derivada por golpe
4. escribir un mini informe de observabilidad

Features minimas:
- peak
- initial_slope
- area_5ms
- area_15ms
- time_to_peak
- tail_ratio
- ioi_prev
- pre_hit_energy

Entregables:
- `hits.parquet` o tabla equivalente
- resumen de separabilidad

Criterio de cierre:
queda claro si la infraestructura actual ya permite mejorar:
- monotonicidad dinamica
- continuidad timbrica
- memoria temporal

Y tambien queda claro que cosas no se pueden inferir con honestidad aun.

### Etapa 4. `StateMapV1` offline usando la infraestructura actual
Objetivo:
mejorar continuidad y memoria temporal sin esperar hardware nuevo.

Modelo permitido en esta etapa:
- energia residual
- contacto/muteo grueso
- regimen temporal

Modelo explicitamente postergado:
- posicion espacial fina
- contacto fisico preciso
- reconstruccion modal rica

Acciones:
1. implementar `legacy_map` y `state_map_v1`
2. correr A/B sobre datasets grabados
3. ajustar `PatchProfile`
4. medir monotonicidad, continuidad y decay

Entregables:
- primer modelo interpretable
- comparacion offline contra legacy

Criterio de cierre:
el modelo nuevo mejora algo real y medible sin requerir cambios de hardware.

### Etapa 5. Integracion live limitada
Objetivo:
probar el modelo nuevo en tiempo real, pero todavia dentro de una via controlada.

Acciones:
1. crear `RendererAdapter` para el engine actual
2. habilitar comparacion A/B en laboratorio
3. probar muteo por software, continuidad y secuencias repetidas
4. mantener separada la app operativa

Entregables:
- comparacion live limitada
- evidencia perceptiva y tecnica

Criterio de cierre:
ya se puede decidir si conviene llevar algo del laboratorio a produccion.

### Etapa 6. Solo si aparece un limite duro: hardware posterior
Objetivo:
abrir una etapa posterior de hardware unicamente si la infraestructura actual queda objetivamente corta.

Condicion para entrar:
- los datos muestran que hay variables importantes invisibles con el setup actual
- `StateMapV1` ya exprime al maximo la infraestructura actual

Orden posterior recomendado:
1. separar piezos por canal
2. repetir protocolo
3. recien despues evaluar sensor adicional o placa distinta

Importante:
esta etapa no es parte del trabajo prioritario actual.

## Resumen ejecutivo por prioridad

### Prioridad inmediata
1. laboratorio minimo
2. logging
3. replay
4. perfiles de parche
5. features
6. `StateMapV1` offline

### Prioridad posterior
1. integracion live limitada
2. solo si hace falta: cambios de hardware

## Regla de oro
Primero optimizar lo que ya existe.
Despues medir si realmente falta algo.
Recien al final abrir la etapa de hardware.
