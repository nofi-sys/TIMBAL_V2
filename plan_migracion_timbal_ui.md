# Plan de migración a arquitectura modular (con paridad 1:1 de funciones)

**Objetivo:** conservar exactamente el comportamiento de tu app actual (audio, MIDI, serial y UI funcional) mientras se adopta la **arquitectura nueva** (QMainWindow + páginas) y se corrigen problemas de usabilidad/estilo. Este documento es una **lista de pasos operativos** para que los agentes ejecuten, uno por vez, sin escribir funcionalidades nuevas hasta alcanzar la paridad.

---

## 0) Reglas de oro
- **Paridad estricta**: el audio y los controles deben sonar/actuar igual que en la versión original antes de refactorizar.
- **Sin inventos**: cualquier cambio de comportamiento necesita ticket propio y aprobación.
- **Refactor envolvente**: mover y encapsular; no reescribir lógica que ya funciona.
- **Reversibilidad**: mantener `--legacy-ui` operativo hasta el final de la migración.

---

## 1) Preparación (1 sola vez)
1. Crear branch `ui-refactor-paridad` desde `main`.
2. Etiquetar la versión que hoy funciona como `v-legacy-ok`.
3. Congelar dependencias en `requirements.txt` (versión exacta de PyQt5, mido, pyserial, pyFluidSynth).
4. Confirmar que la carpeta `fluidsynth_dlls/` está en la raíz del repo y **en el .gitignore NO** (debe versionarse si es legal).
5. En Windows: documentar ruta y versión de las DLLs.

---

## 2) Mapa del código (origen → destino)

| Origen (archivo/clase/función) | Nuevo destino | Acción |
|---|---|---|
| **Fluidsynth DLL bootstrap** (bloque superior del archivo legacy) | `app/audio/bootstrap_fluidsynth.py` | Mover tal cual. Debe **inyectar `fluidsynth_dlls` al PATH** antes de importar `fluidsynth`. |
| **SoundEngine** (clase completa) | `app/audio/engine_legacy.py` | Copiar **sin cambios**. Exportar la misma API pública usada por la UI. |
| `load_config`, `save_config`, `_app_config_dir` | `app/state/settings.py` | Copiar sin cambios. Mantener `CONFIG_PATH` y esquema JSON actual. |
| **NoteSelectorDialog** | `app/ui/components/note_selector.py` | Copiar sin cambios. |
| **Vu** | `app/ui/components/vu.py` | Copiar sin cambios. El ancho fijo puede relajarse más adelante. |
| **DrumPadController._abrir_arduino** | `app/io/arduino.py` (`open_arduino()`) | Copiar sin cambios por ahora. Devolver `serial.Serial` o `None`. |
| **DrumPadController._abrir_midi** | `app/io/midi.py` (`open_midi_in()`) | Copiar sin cambios por ahora (modo polling si existe). |
| **Serial/MIDI loop** (`_timer_vu` + `_leer_serial`) | `app/io/reader.py` (`SerialReader(QThread)`) | Copiar lógica tal cual; solo envolver en señales Qt (`on_hit`, `on_analog`) que consumirá la UI. |
| **Preset reverb** (`_preset_reverb`) | `app/ui/pages/effects_presets.py` | Copiar sin cambios. |
| **Cargar SF2** (`_cambiar_sf2`) | `app/ui/pages/devices.py` (o en menú superior) | Copiar sin cambios; reusar `SoundEngine.load_sf2_live`. |
| **Botones/labels de notas**, `_to_midi`, mapeo HW | `app/ui/pages/pads.py` | Copiar sin cambios. |
| **Main window legacy** | `legacy/legacy_app.py` | Dejar operativo para fallback. |

> Importante: durante la fase de paridad, **la UI nueva consumirá directamente `engine_legacy.SoundEngine`**. El engine “dummy” solo se usa en entornos de desarrollo sin FluidSynth.

---

## 3) Plan paso a paso (checklist ejecutable)

### Fase A – Base estable y audio idéntico
1. **Integrar bootstrap de DLLs**: mover el bloque de PATH a `app/audio/bootstrap_fluidsynth.py` y llamarlo desde `engine_legacy.py` antes del `import fluidsynth`.
2. **Copiar `SoundEngine`** tal cual a `app/audio/engine_legacy.py`. No tocar fórmulas de `master_db`, `set_gain`, `ATTENUATION`, ni el escalado de velocity.
3. **Cambiar la UI nueva para usar `engine_legacy.SoundEngine`**. No usar el engine dummy en esta fase.
4. **Prueba de humo**: correr `--new-ui`, cargar el mismo `.sf2` que en legacy y validar: a) suena, b) niveles parecidos, c) sin mutear al mover master.

### Fase B – Controles originales en su sitio
5. **Crear `EffectsPage` temporal con los mismos widgets** que el legacy (checkbox + sliders Reverb Level/Room/Damp; Boost; Master; Limitador; Gate; Brillo CC74).
6. **Conectar cada control a los mismos métodos** que en legacy (misma firma, mismo orden de llamadas). Ejemplo: el slider de Level debe replicar la función `_apply_reverb_level` (incluyendo el ajuste de `set_reverb_send` y `set_reverb_active`), pero **sin reescribir la lógica**: copiar la secuencia y referencias a `self.audio` tal cual.
7. **Master siempre visible**: mover el control de Master dB a un **panel superior** dentro de `PadsPage` (no en otra ventana). Solo reubicar el widget; el slot sigue siendo `SoundEngine.set_master_gain_db`.
8. **Presets de reverb**: añadir tres botones (“Seco/Media/Sala”) que llamen exactamente a `_preset_reverb` copiada. Deben ajustar los valores de sliders y actualizar el engine.

### Fase C – I/O y VU
9. **Mover `Vu` a componente** y usarlo tal cual en `PadsPage`. No modificar tiempos, colores ni decaimiento todavía.
10. **Serial/MIDI**: portar `_abrir_arduino` y `_abrir_midi` a `app/io`. Mantener los prints/logs y la selección automática de puerto “Arduino”.
11. **Loop de lectura**: copiar `_timer_vu` + `_leer_serial` tal cual dentro de un `QThread` que emite señales. Conectar esas señales a: a) actualizar VUs, b) disparar notas vía `SoundEngine.disparar`.
12. **MIDI passthrough**: respetar `TIMBAL_MIDI_PASSTHROUGH` exactamente; no invertir la lógica.

### Fase D – Navegación y persistencia mínima
13. **Navegación**: en el `QStackedWidget`, mostrar por defecto **Pads** y a la derecha (o debajo) **Efectos**; la columna izquierda puede quedar simple por ahora.
14. **Persistencia**: portar `CONFIG_PATH` y recordar al menos `last_sf2` y los valores actuales de sliders (mismo formato JSON). No cambiar nombres de claves.
15. **Status bar**: replicar los mensajes informativos (cambio de SF2, reconexión, preset aplicado). No introducir popups extra.

### Fase E – Visual/coherencia sin romper paridad
16. **Tema**: aplicar QSS solo para **contraste y legibilidad** (texto blanco sobre fondos oscuros). No modificar tamaños de controles.
17. **Colores de texto**: verificar que labels y botones (especialmente en `QGroupBox`) tengan color de texto legible (blanco o gris claro). Ajuste puntual de `color:` en QSS.
18. **Left nav**: mantenerlo simple, pero agregar íconos básicos para distinguir secciones (sin cambiar la lógica).

### Fase F – QA de paridad y bugs reportados
19. **Caso “subí Master y se cortó”**: validar que `set_master_gain_db` y `_apply_master_gain_locked` son los **originales**. Confirmar que no se combinan con un “extra boost” alternativo. Si hay ATTENUATION, respeta la fórmula y rangos previos.
20. **Caso “no suena tras reiniciar”**: revisar que los valores persistidos no graben `master_db` fuera de rango. Limitar en la UI (mismos rangos legacy) y al cargar configuración.
21. **Volumen siempre a mano**: confirmar que Master dB está presente en Pads y en Efectos. Moverlo **no cambia** su conexión.
22. **Plan de regresión**: repetir pruebas de: reverb ON/OFF, presets, brillo CC74, Gate, Boost, reconexión I/O, carga de SF2 en caliente, maximizar ventana.

---

## 4) Coordinación entre agentes
- **Unidad de trabajo mínima**: 1 PR por paso (o subpaso), con captura de pantalla y breve video si es UI.
- **Contrato de interfaces**: publicar la firma exacta de métodos usados por la UI (documento corto). Cualquier cambio exige consenso.
- **Pruebas manuales guionadas**: checklist del punto 3 y 5. Marcar "OK"/"Falla" en cada PR.
- **Logs**: dejar `print` como está en paridad. Unificar a `logging` al final de la migración.

---

## 5) Definición de “Done” para paridad
- La app en `--new-ui` **suena igual** (mismo nivel percibido) que `--legacy-ui` con el mismo `.sf2`.
- Todos los sliders/botones **hacen exactamente lo mismo** que antes (demostrado en video corto por sección).
- Reinicio de la app **no rompe** audio ni deja mudo el motor.
- Master dB está **siempre visible** en Pads. Los textos son **legibles** en todos los widgets.

---

## 6) Próximo sprint (después de paridad)
- Mejorar left nav (íconos, tipografía, estados hover/active).
- Página **Dispositivos** (lista de MIDI/Serie, reconectar desde ahí).
- Página **Presets** (guardar/cargar JSON legible). Sin cambiar sonido por defecto.
- Migrar loop de polling a señales/slots (`QThread`) con cancelación limpia.

