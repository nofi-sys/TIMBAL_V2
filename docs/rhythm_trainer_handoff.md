# Rhythm Trainer · Handoff

## Objetivo de esta rama de trabajo
Crear un programa paralelo, independiente de la pantalla de configuracion principal, orientado al aprendizaje ritmico con el timbal como controlador.

## Estado base ya implementado
- Entry point: `main.py --run-trainer`
- Launcher rapido: `run_timbal.bat trainer`
- Ventana dedicada en `app/trainer/window.py`
- Core del loop y metricas en `app/trainer/core.py`
- Usa el mismo motor de audio y el mismo tema visual base que la app principal
- Usa el mismo router de input compartido (`app/io/timbal_input.py`)

## Alcance actual
- Patron fijo: 4/4
- Un golpe en cada negra
- Cuadrados en movimiento hacia la zona de golpe
- Metricas minimas:
  - perfect
  - good
  - miss
  - offbeat
  - racha
  - promedio de error en ms
  - porcentaje de precision
  - compases completados
- Fallback manual con tecla `Espacio`

## Restricciones actuales
- No toca configuracion persistente del usuario.
- Usa SoundFont bundled; no abre la UI de presets/efectos.
- No intenta editar mappings ni parametros del timbal.

## Reglas para seguir expandiendolo
- Mantener todo lo nuevo del trainer dentro de `app/trainer/` salvo utilidades realmente compartidas.
- Si se necesita UI reutilizable, extraer componentes neutrales y documentar el movimiento.
- No mezclar logica de entrenamiento con `PadsPage`.

## Proximas mejoras sugeridas
1. Selector temporal de BPM y count-in dentro del trainer.
2. Mas patterns:
   - corcheas
   - silencios
   - acentos
   - patrones folkloricos
3. Feedback visual mas expresivo:
   - adelantado/tarde a izquierda/derecha
   - colores por grado
4. Sesiones finitas con resumen final.
5. Persistencia propia del trainer en archivo separado cuando haga falta.
