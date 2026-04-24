# Checklist consolidado del primer sprint

## Objetivo del sprint
Sacar una linea experimental usable usando la infraestructura actual, sin comprar nada ni depender de firmware nuevo para arrancar.

## Resultado esperado
- existe `--run-timbal-lab`
- el laboratorio abre sin romper la app principal
- se puede grabar una sesion completa
- se puede hacer replay
- se obtiene el primer perfil de parche
- se puede comparar `legacy_map` contra un `state_map_v1` minimo

## Dia 1. Abrir el laboratorio

### Tareas
1. Agregar `--run-timbal-lab` en `main.py`.
2. Crear `app/timbal_lab/`.
3. Crear `app/timbal_lab/ui/window.py`.
4. Reutilizar `build_application()` y `build_audio_engine()` desde `app/runtime.py`.
5. Envolver el experimento actual como `AnalogRawSource`.

### Criterio de listo
- el laboratorio abre
- no afecta `--new-ui`, `--legacy-ui` ni `--run-host-analog`
- el laboratorio detecta si hay fuente analogica disponible

## Dia 2. Logging y sync con infraestructura actual

### Tareas
1. Implementar `SessionRecorder`.
2. Guardar:
   - `manifest.json`
   - `arduino_raw.bin`
   - `events.jsonl`
3. Agregar accion `SYNC` desde host:
   - flash visual
   - click corto
   - evento logueado
4. Agregar toggle `Mute SW ON/OFF`.

### Metadata minima por sesion
- fecha y hora
- parche
- afinacion
- sketch / firmware usado
- fuente activa
- notas del experimento

### Criterio de listo
- se puede grabar una sesion de 30 a 60 segundos
- la sesion queda legible y reutilizable
- no hubo que tocar el firmware operativo principal

## Dia 3. Replay, features y primer benchmark

### Tareas
1. Implementar `ReplaySource`.
2. Implementar features basicas:
   - peak
   - initial_slope
   - area_5ms
   - area_15ms
   - time_to_peak
   - tail_ratio
   - ioi_prev
   - pre_hit_energy
3. Crear `patch_A.yaml` o equivalente.
4. Implementar `legacy_map`.
5. Implementar un `state_map_v1` minimo offline.
6. Comparar ambos con un microdataset.

### Microdataset minimo
- 3 dinamicas
- 3 repeticiones por dinamica
- 2 tipos de gesto si se puede

### Criterio de listo
- existe replay offline
- existe tabla de features
- existe un perfil de parche
- existe comparacion minima `legacy_map` vs `state_map_v1`

## Checklist de control

### Antes de empezar
- baseline anotado
- carpeta de sesiones creada
- parche identificado
- afinacion anotada

### Durante la captura
- el stream entra
- el timestamp host se registra
- `SYNC` queda logueado
- la sesion se cierra correctamente

### Despues de la captura
- existe `manifest.json`
- existe `arduino_raw.bin`
- existe `events.jsonl`
- se puede abrir la sesion
- se puede correr replay

## Reglas del sprint

### Regla 1
No comprar nada.

### Regla 2
No bloquearse esperando firmware nuevo.

### Regla 3
No hacer refactor grande de arquitectura compartida.

### Regla 4
No meter machine learning.

### Regla 5
No mezclar laboratorio y app principal.

## Lo que pasa al terminar este sprint
Si el sprint sale bien, el siguiente paso ya no es discutir arquitectura. El siguiente paso es:
1. ampliar dataset
2. ajustar `PatchProfile`
3. mejorar `state_map_v1`
4. recien despues evaluar si la infraestructura actual ya toco techo
