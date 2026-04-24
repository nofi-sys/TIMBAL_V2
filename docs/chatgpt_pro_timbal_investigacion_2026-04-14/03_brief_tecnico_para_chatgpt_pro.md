# Brief tecnico para ChatGPT Pro

## Proyecto
Timbal digital experimental con sensores piezoelectricos, Arduino y software host en Python para interpretacion, mapeo y reproduccion.

## Contexto corto
El proyecto ya tiene trabajo previo sobre latencia, UI y streaming analogico, pero ahora el problema central paso a ser la representacion natural del instrumento. La meta no es solo detectar golpes: es modelar de forma verosimil la relacion entre gesto, energia, timbre, decay, rebote, muteo y acumulacion de energia entre golpes sucesivos.

## Estado actual del sistema
- Sensado actual: tres piezoelectricos en paralelo.
- Captura y control: Arduino.
- Host software: Python.
- UI host: PyQt5.
- Audio y MIDI: stack Python con FluidSynth y rtmidi.
- Ya existe:
  - un roadmap de firmware orientado a latencia
  - un experimento host-side para transmitir analogico crudo y observar la senal

## Problema principal
La respuesta actual no es fisicamente creible ni timbricamente continua.

Sintomas reportados:
- el volumen no siempre representa la fuerza del golpe
- el timbre cambia de manera abrupta entre niveles cercanos de intensidad
- hay saltos demasiado grandes entre rangos medios y altos
- no esta bien representada la diferencia entre golpe corto, golpe retenido y golpe con presion residual
- no hay una buena emulacion de acumulacion de energia en golpes sucesivos
- el muteo no reproduce todavia el comportamiento natural de una mano sobre el parche

## Preguntas de investigacion

### 1. Modelo fisico del timbal
- Como se modela fisicamente el comportamiento de un timbal o una membrana tensada comparable?
- Que variables son imprescindibles para capturar el fenomeno sin caer en una simulacion imposible de correr en tiempo real?
- Como entran en juego:
  - fuerza de impacto
  - ubicacion del golpe
  - duracion del contacto
  - rebote de la baqueta
  - presion residual
  - apagado por contacto
  - acumulacion de energia en golpes sucesivos
  - estructura de armonicos y cambios de timbre

### 2. Capacidad real del hardware actual
- Hasta donde se puede llegar usando solo tres piezoelectricos y Arduino?
- Que variables del comportamiento real son observables con esa configuracion?
- Que variables no pueden inferirse con suficiente confiabilidad?
- Que sensor extra de bajo costo agregaria mas informacion util si hiciera falta una mejora puntual?

### 3. Estrategia de modelado
- Conviene un enfoque hibrido?
- Como combinar:
  - heuristicas temporales
  - modelo fisico reducido
  - calibracion empirica por parche
  - machine learning o aprendizaje supervisado
- Tiene sentido explorar SVM, regresion no lineal, modelos de estado, filtros, identificacion de sistemas o redes pequenas?
- Que enfoque es realista en costo, mantenimiento y robustez?

### 4. Reglas temporales
- Como representar matematicamente la dependencia temporal del instrumento?
- Como modelar la acumulacion de energia entre golpes?
- Como modelar el muteo parcial o total por contacto sostenido?
- Como modelar la transicion timbrica entre ataques cortos, ataques retenidos y rebotes naturales sin saltos bruscos?

### 5. Experimentos de calibracion
- Que experimento minimo y barato permitiria levantar datos utiles?
- Como sincronizar:
  - video superior del punto de impacto
  - video lateral del gesto
  - telemetria Arduino
  - captura de pantalla del software
- Que variables conviene registrar?
- Como estructurar el dataset resultante para calibracion y validacion?

### 6. Arquitectura de software para investigacion
- Conviene extender la app actual o hacer una app paralela de analisis?
- Que modulos deberia tener esa version experimental?
- Como preparar el software para:
  - registrar datos crudos
  - reproducir o etiquetar golpes
  - comparar prediccion vs resultado
  - iterar rapido sobre modelos

## Restricciones
- Bajo presupuesto.
- Priorizar hardware ya disponible.
- Aceptar una compra puntual solo si aporta valor reutilizable.
- Evitar propuestas academicamente lindas pero imposibles de operar en tiempo real o de mantener.
- No simplificar la fisica solo para hacerla mas facil de explicar.

## Entregables esperados de ChatGPT Pro
Pedir una respuesta con estas partes:

1. Diagnostico del problema en lenguaje tecnico, separando lo que surge de fisica conocida y lo que es inferencia.
2. Modelo conceptual del instrumento con variables, relaciones y, donde sirva, ecuaciones o aproximaciones utiles.
3. Evaluacion honesta de si el hardware actual alcanza y que informacion falta.
4. Propuesta de enfoque hibrido de modelado, con ventajas y desventajas.
5. Diseno de uno o mas experimentos de bajo costo para calibrar el sistema.
6. Recomendacion concreta de arquitectura experimental de software.
7. Roadmap por etapas con criterio costo-beneficio.
8. Bibliografia o referencias primarias relevantes.

## Material adjunto sugerido
- Este brief.
- `02_diario_estado_actual.md`
- `06_objetivos_cambios_y_experimentos.md`
- `C:\MUSICA\TIMBAL_V2\docs\arduino_timbal_roadmap.md`
- `C:\MUSICA\TIMBAL_V2\docs\host_analog_experiment.md`
- `01_transcripcion_limpia_audio.md` si hace falta mas contexto fino.
