# Objetivos, cambios de software y experimentos

## Objetivos de investigacion

### Objetivo 1
Eliminar las discontinuidades artificiales entre fuerza de golpe, volumen y timbre.

### Objetivo 2
Modelar de forma mas natural:
- ataque corto
- ataque retenido
- presion residual
- muteo
- acumulacion de energia entre golpes sucesivos

### Objetivo 3
Determinar si el hardware actual permite ese modelado o si hace falta alguna mejora puntual.

### Objetivo 4
Preparar una version experimental del software que permita medir, registrar y comparar modelos sin perder la version operativa actual.

## Cambios de software pedidos o sugeridos en el audio

### Cambios minimos de soporte
- Agregar soporte explicito al boton de muteo.
- Agregar un modo para desactivar el muteo desde software y poder testear parches sin ese boton.
- Recuperar o rehacer la logica de decay del muteo para que se parezca al apagado real del timbal.

### Cambios para investigacion
- Habilitar mayor plasticidad del software para probar distintos modelos de mapeo.
- Permitir registrar datos crudos y datos ya procesados.
- Permitir comparar distintos algoritmos con el mismo conjunto de golpes.
- Evaluar si conviene una version experimental paralela dedicada a analisis y calibracion.

### Posibles cambios de interfaz o control
- Diferenciar boton del parche y pedal externo.
- Evaluar si ambos pueden compartir una misma linea con senales distinguibles.
- Pensar futuras acciones del pedal:
  - muteo
  - cambio de set
  - cambio de tonalidad
  - otras acciones especiales

## Preparacion del software para experimentos

### Preparacion recomendada antes de programar
1. Resguardar la version actual del software.
2. Elegir si el trabajo experimental va en una copia paralela o en una rama separada.
3. Identificar un punto de entrada de modo experimental.
4. Separar claramente:
   - captura de datos
   - logging
   - visualizacion
   - evaluacion del modelo
   - reproduccion sonora

### Capacidades que la version experimental deberia tener
- Logging con timestamps confiables.
- Registro de valores crudos del Arduino.
- Registro de eventos derivados por el algoritmo.
- Herramientas para etiquetar pruebas por parche, afinacion y tipo de golpe.
- Reproduccion repetible de configuraciones y parametros.
- Comparacion entre salida esperada y salida observada.

## Experimentos de hardware pedidos o sugeridos

### Experimento 1. Validacion del campo de sensado
- Representar geometricamente el parche o semicirculo.
- Marcar posicion de sensores.
- Golpear en ubicaciones controladas.
- Observar como cambia la senal segun posicion y fuerza.

### Experimento 2. Sincronizacion gesto-senal-resultado
- Camara superior para ubicar el punto de impacto.
- Camara lateral para ver velocidad y contacto.
- Patron visual o grilla de calibracion.
- Captura simultanea de pantalla del software.
- Registro simultaneo de telemetria del Arduino.

### Experimento 3. Muteo y contacto sostenido
- Comparar golpe con retiro rapido de baqueta vs golpe con permanencia o presion residual.
- Medir diferencias de decay, espectro aparente y amplitud.
- Ver si los sensores actuales capturan esa diferencia o si queda invisible.

### Experimento 4. Energia acumulada
- Ejecutar secuencias repetidas con fuerza similar.
- Medir si el sistema detecta o puede modelar crecimiento de energia aparente.
- Comparar contra percepcion auditiva del instrumento real.

## Preguntas que estos experimentos tienen que resolver
- Que variables observables se pueden extraer realmente del hardware actual.
- Que parte del comportamiento del timbal conviene modelar por fisica simplificada.
- Que parte conviene resolver por calibracion o aprendizaje.
- Si hace falta un sensor adicional, cual daria mas informacion por menor costo.

## Criterio de decision
Toda propuesta posterior deberia juzgarse por:
- realismo perceptivo
- estabilidad
- latencia
- costo
- facilidad de iteracion
- facilidad de mantenimiento
