# Patch diagnostic protocol

## Goal
Find out whether brutal volume jumps come from the physical patch/electronics, from firmware hit detection, or from the sound/rendering layer.

Do not start from the trainer. The trainer is downstream from too many things. Start from raw Arduino samples, then move upward.

## Decision rules
- If fixed MIDI/UI hits at the same velocity sound uneven, the issue is in the audio engine, soundfont, bank/preset, gain, or velocity layers.
- If fixed MIDI/UI hits are stable but raw peaks/areas vary strongly for equal-force hits, the issue is mechanical or electrical before software.
- If raw peaks/areas are stable but runtime `HIT` velocity jumps, the issue is firmware thresholding, baseline/noise tracking, refractory, or velocity mapping.
- If each piezo node is stable alone but the parallel sum is unstable, the issue is summing: polarity, loading, cross-coupling, cable/noise, or mechanical phase/timing.
- If center hits are stable and edge hits are not, the issue is patch geometry/support/contact, not the soundfont.

## Hardware caveats to watch
- Piezo discs are capacitive sources, not ideal sensors. Putting several directly in parallel can make them load each other.
- "Phase" here usually means polarity inversion, timing smear, or destructive summing of the first transient lobe, not musical audio phase.
- If one node bends opposite to another, the first lobe can invert. In a parallel network that can shrink the summed peak even when the physical hit was strong.
- The Arduino analog pin cannot read negative voltage. Use the same protection/bias network in every A/B test, or the test will lie.
- For multichannel tests, independent channels are better than a summed graph because they show which piezo fired, with what polarity/timing.

## Tools in this repo
- Single-channel raw stream: `arduino/HOST_ANALOG_STREAM_EXPERIMENT.ino`
- Multichannel raw stream: `arduino/HOST_ANALOG_STREAM_MULTICHANNEL.ino`
- Host analog view: `run_timbal.bat analog`
- Timbal Lab capture/analysis: `run_timbal.bat lab`
- Runtime firmware comparison: `arduino/TIMBAL_RUNTIME_PRESENCE_V1.ino`

## Test 0: prove the renderer is not the random part
1. Open the app with the normal runtime, without changing the patch.
2. Trigger the UI hit button or a fixed MIDI note at velocity 60 ten times.
3. Repeat at velocity 90 and 120.
4. If those are stable, the brutal jump is probably before the audio layer.
5. If velocities near one boundary sound like two completely different instruments, document that boundary as a soundfont layer problem.

## Test 1: one piezo, one location, raw signal
1. Flash `HOST_ANALOG_STREAM_EXPERIMENT.ino`.
2. Connect only one piezo to A0.
3. Open `run_timbal.bat lab`.
4. Source: Analog Raw.
5. Patch ID: `p1_single_a0_center`.
6. Notes: `20 center hits, same force, one piezo only`.
7. Start source, start session, hit 20 times, close session, run analysis.

Expected reading: `peak_value`, `absolute_peak_value`, `area_5ms`, `initial_slope`, and `dominant_polarity` should be reasonably consistent. If they are already all over the place, the problem is not the trainer.

## Test 2: same piezo, map the patch
Use the same single-piezo wiring. Record separate sessions so the label is unambiguous:

- `p1_single_a0_center`
- `p1_single_a0_edge_north`
- `p1_single_a0_edge_south`
- `p1_single_a0_edge_east`
- `p1_single_a0_edge_west`
- `p1_single_a0_between_nodes`

Do 15 to 20 hits per zone. The question is whether the same force produces similar raw area and peak across the playing surface.

## Test 3: piezo nodes before summing
1. Flash `HOST_ANALOG_STREAM_MULTICHANNEL.ino`.
2. Wire nodes separately: A0, A1, A2, A3, A4.
3. Open `run_timbal.bat lab`.
4. Patch ID: `p1_nodes_separate`.
5. Hit the same marked locations as Test 2.
6. Run analysis and compare channels.

What to look for:
- A nearby node should usually show the largest first transient.
- Polarity should not randomly flip between nodes unless the discs or mounts are mechanically/electrically inverted.
- If several channels fire with different first-lobe polarity, summing them directly can create a smaller or stranger combined signal.

## Test 4: summed graph in parallel
1. Restore the triangular/graph parallel wiring into one analog input.
2. Flash `HOST_ANALOG_STREAM_EXPERIMENT.ino`.
3. Record the same zones again as `p1_parallel_sum_*`.
4. Compare raw features against Test 3.

If separate nodes are strong but the summed version sometimes collapses, the graph is the suspect. Try an A/B test with one piezo polarity reversed, or add isolation/protection components in a controlled electronics pass before deciding the final circuit.

## Test 5: firmware comparison
1. Flash `TIMBAL_RUNTIME_PRESENCE_V1.ino`.
2. Record or observe `HIT` velocity for the same center test.
3. Compare firmware velocity to raw `absolute_peak_value` and `area_5ms` from the raw session.

If raw intensity is smooth but firmware velocity jumps between very low and very high, tune firmware detection first: baseline, threshold multiplier, min threshold, deviation clamp, and velocity curve.

## First run to do now
Start with Test 1 and Test 2 using only one connected piezo/input. That answers the most important question fast: whether the raw electrical signal is stable before we blame the graph or the software.
