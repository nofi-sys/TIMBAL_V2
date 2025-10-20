# Timbal Digital · Roadmap técnico de firmware Arduino
**Objetivo**: eliminar latencia perceptible del golpe al sonido y agregar un modo **tremolo-aware** que adapte umbrales/refractario durante redobles, manteniendo robustez frente a ruido y crosstalk. Documento pensado como checklist operativo para agentes (sin código, sólo pasos).

---

## 0) Principios
- **Paridad**: no cambiar la “sensación” de dinámica lograda; solo acelerar la ruta crítica y estabilizar detecciones.
- **Hot-path mínimo**: nada de `delay()`, `flush()`, JSON ni operaciones pesadas en el camino del `note_on`.
- **Medir siempre**: cada sprint debe registrar latencia (μs/ms), tasa de falsos positivos y pérdida de golpes.

---

## 1) Ruta crítica de latencia (del golpe al Note On)
### A. Captura (ADC y filtrado) — Impacto: **alto**
- Migrar a **ADC free‑running** con ISR (interrupción) a período fijo (p.ej. 2 kHz–4 kHz por canal efectivo).
- Mover la lectura de sensores a **buffer circular**; todas las decisiones de onset leen del buffer (no de `analogRead()`).
- Filtrado ligero en hot‑path: **HPF** (o sustracción de línea base) + **EMA** (exponencial) con coeficientes fijos enteros (fixed‑point).

### B. Onset (detección del golpe) — Impacto: **alto**
- Disparar `note_on` cuando **cruce de umbral** con **histéresis** y **refractario (dead‑time)** en ticks.
- **Velocity por pendiente**: estimar `vel ≈ k * dV/dt` usando 2–3 muestras iniciales; **no** esperar el pico para disparar.
- Ventana de **inhibición de rebote**: 1–2 ms post‑onset ignoran re‑onsets hasta que la pendiente vuelva a superar `minSlope`.

### C. Transporte del evento — Impacto: **muy alto**
- Para golpes: **USB‑MIDI class‑compliant** o **protocolo binario** (3–7 bytes). **Evitar JSON** en hot‑path.
- **Prohibido** `flush()` tras cada envío; si el stack lo requiere, programar `flush` periódico (cada 2–4 ms) fuera del hot‑path.
- Timestamp local (ticks ms/μs) incluido en cada evento para diagnóstico.

### D. Recomendación host (PC) — Impacto: **medio**
- Backend: puerto **MIDI** (rtmidi) directo, sin parser JSON.
- Opción de **micro‑corrección** tras 5–8 ms con **CC11 (Expression)** por canal de pad (si cada pad usa su canal), evitando re‑disparo.

**Criterio de éxito**: latencia Arduino→NoteOn host ≤ **1–3 ms** típicos (sin síntesis), y total sistema (incluyendo FluidSynth) ≤ **10 ms** con buffers ajustados.

---

## 2) Tremolo‑aware (máquina de estados)
### Estados por pad
- `NORMAL` → `TREM_SUSPECT` → `TREM_CONFIRMED` → `NORMAL`

### Detección y transición
- Calcular **IOI** (Inter‑Onset Interval) en ms con timestamp local.
- Si se reciben ≥2 golpes con IOI en **66–125 ms** (≈ 8–15 Hz) y **varianza < 15 ms** → `TREM_CONFIRMED`.
- Salida: **> 300 ms** sin golpes o ≥2 IOI fuera de rango → volver a `NORMAL` (con interpolación de parámetros en 2–3 pasos para evitar saltos).

### Parámetros por estado
- `NORMAL`: `thr=T0`, `refract=R0` (12–18 ms), `minSlope=S0` (2–4× ruido HF).
- `TREM_CONFIRMED`: `thr=0.6·T0`, `refract=0.5·R0`, `minSlope=0.7·S0` (+ leak mayor en seguidor de envolvente).
- Comprimir dinámicas en tremolo (anti “metralleta”): `v = 127·(1 − e^(−k·slope))` ó limitar delta‑v sucesivos.

### Antidoble y crosstalk
- Ventana post‑onset (1–2 ms) que ignora re‑onsets si la pendiente no supera `minSlope` nuevamente.
- Inhibición lateral: leve aumento de umbral en pads **vecinos** por **50–80 ms** tras un onset real.

---

## 3) Protocolo de eventos (para reemplazar JSON en golpes)
### Opción A — USB‑MIDI (preferida)
- `Note On`: canal = `MIDI_CH_OF[i]`, `note = mapping[i]`, `velocity = 1–127` (derivada inicial).  
- Opcional: a los **5–8 ms** mandar `CC11` (Expression) en el **mismo canal** para afinar el nivel sin re‑disparar.
- `Note Off`: al expirar `auto_off` o al detectar mute/fin de envolvente.

### Opción B — Serial binario compacto (si no hay MIDI)
- **Golpe (0xA1)**: `A1 | pad(0–7) | vel(1–127) | t_low | t_high | flags | chk`  
  - `t_low/t_high`: timestamp de 16 bits en ms (mod 65536) o ticks a 0.5 ms.  
  - `flags` bits: b0= tremolo, b1= retrigger_ok, b2= clipped, b3= neighbor_inhibit, b7..b4 reservados.  
  - `chk`: suma de los bytes previos mod 256.
- **Mute (0xB1)**: `B1 | pad | state(0/1) | t_low | t_high | chk`
- **Analog debug (0xC1)**: `C1 | pad | sample_low | sample_high | t_low | t_high | decim | chk` (enviar 1 de cada N).

**Regla**: los frames de telemetría se pueden desactivar en producción; los de golpe son mínimos y constantes.

---

## 4) Debounce y coherencia de mute
- Implementar **debounce temporal** (5–10 ms) por botón con contador de estabilidad antes de cambiar `btnNow/btnPrev`.
- Al mutear: mandar `note_off` inmediato **sin `flush`** y latchear `muteLatched[i]=true` con timestamp; ignorar hits en una ventana corta de cola.
- Al desmutear: restaurar `exprTarget[i]=EXP_MAX` y borrar estados de envolvente (`envFollow/envArmed`) coherentemente.

---

## 5) Parámetros iniciales sugeridos (por pad)
- `T0` (umbral normal): 12–18% de escala (post‑HPF/EMA), ajustado por pad.
- `R0` (refractario normal): 12–18 ms.
- `S0` (pendiente mínima): 2–4× ruido HF medido.
- Rango tremolo: IOI 66–125 ms; confirmación con 2–3 IOI; salida > 300 ms sin golpes o 2 IOI fuera de rango.
- Inhibición lateral: +10–20% de umbral en vecinos por 50–80 ms.

---

## 6) QA y métricas (cada PR debe incluir)
- **Latencia** Arduino→Host (ms): medido con timestamp en evento + recepción en PC (delta). Meta: ≤ 3 ms p95.
- **Pérdida de golpes** a 8–15 Hz: 0% en 30 s por pad.
- **Falsos positivos** en silencio: ≤ 1 por 5 min/pad.
- **Simetría de dinámica**: comparación con versión anterior (curva vel→nivel en host).

**Pruebas dirigidas**:
1) Single hits suave/medio/fuerte (20 repeticiones).  
2) Tremolo 8–15 Hz continuo 30 s.  
3) Mute/unmute durante tremolo (sin colarse golpes).  
4) Crosstalk: golpear pad A con B/C cerca (sin falsos).

---

## 7) Roadmap para agentes (orden recomendado)
1) **Transporte**: USB‑MIDI o binario (quitar JSON en golpes) + **eliminar `flush` del hot‑path**.  
2) **ADC free‑running** + buffer circular + onset por umbral/histéresis/refractario + pendiente para velocity (fixed‑point).  
3) **Máquina de estados de tremolo** con parámetros del §2.  
4) **Debounce mute** + coherencia de estados y timeouts.  
5) **Telemetría** (frames A1/B1/C1) con toggle de compilación.  
6) Ajustes finos (inhibición lateral, CC11 micro‑corrección).

Cada paso → 1 PR con: descripción, dif de parámetros, métricas (latencia, pérdidas, falsos), y short video/plot.

---

## 8) Riesgos y mitigación
- **Bloqueos ocultos** (p.ej. `midiFlush()`): revisar llamadas en ISR/loop; mover a scheduler suave.
- **Drift de timestamp**: sincronizar origen de tiempo (overflow 16‑bit); en host corregir con mod‑wrap.
- **Sobre‑sensibilidad en tremolo**: limitar reducción de umbral a 0.6·T0 y volver en 2–3 pasos.

---

## 9) Entregables del sprint
- Firmware con flags: `USE_MIDI`, `USE_BIN_PROTO`, `DEBUG_TELEM`.
- Tabla de parámetros por pad (`T0, R0, S0`) versionada en JSON/YAML.
- Informe QA con 4 pruebas del §6 y curvas vel→nivel comparadas con legacy.

