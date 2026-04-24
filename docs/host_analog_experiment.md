# Host Analog Experiment

## Objetivo
Probar una variante donde el Arduino no detecta el golpe sino que transmite muestras analógicas crudas y la PC hace la detección.

## Veredicto esperado antes de medir
Esto es útil para:
- visualizar la señal real
- estudiar umbrales, rebotes y dinámica
- comparar sensibilidad de algoritmos

No debería asumirse como camino final de menor latencia. En general:
- firmware-side onset + evento corto sigue siendo el camino más rápido
- host-side analog suele agregar transporte, buffering y jitter

## Lo que ya quedó listo
- Ventana del experimento: `run_timbal.bat analog`
- Entry point: `main.py --run-host-analog`
- Lector binario host-side en `app/host_analog/stream.py`
- UI/visualización en `app/host_analog/window.py`
- Sketch experimental en `arduino/HOST_ANALOG_STREAM_EXPERIMENT.ino`

## Protocolo binario
Frame fijo de 8 bytes, little-endian:
- `0xA1`
- `channel`
- `micros()`
- `analog value`

Esto evita JSON y texto para no sesgar la prueba con overhead innecesario.

## Flujo de prueba
1. Guardar el firmware actual del Arduino.
2. Flashear `HOST_ANALOG_STREAM_EXPERIMENT.ino`.
3. Abrir `run_timbal.bat analog`.
4. Ajustar:
   - `Threshold`
   - `Delta`
   - `Refractory`
5. Golpear el parche y observar:
   - waveform
   - valor pico
   - golpes detectados
   - lag estimado

## Métrica de lag
El lag mostrado es una estimación host vs timestamp `micros()` del Arduino. Sirve para comparar modos, no como medición absoluta de extremo a extremo.

## Riesgos
- Si el stream es demasiado denso, la PC puede quedarse atrás.
- Si se suben muchos canales a la vez, el throughput del protocolo puede volverse el cuello de botella.
- Aunque la sensibilidad pueda mejorar, la latencia total puede no mejorar.
