Tomando tu respuesta anterior como base, ahora quiero que conviertas esa investigacion en una propuesta concreta de implementacion.

No quiero una nueva introduccion teorica. Quiero bajar la teoria a decisiones de arquitectura, experimento y software.

Contexto:
- existe una app host en Python con UI y audio
- existe tambien un experimento host-side analogico
- no quiero perder la version actual del software
- estoy dispuesto a crear una version experimental paralela o una rama experimental si eso resulta mas limpio
- el presupuesto sigue siendo limitado

Necesito que propongas una etapa 2 con este formato:

1. Decision de arquitectura
- conviene extender la app actual o crear una app paralela de analisis
- justifica la decision

2. Modulos concretos que habria que construir
- adquisicion de datos
- sincronizacion y logging
- visualizacion de golpes
- calibracion por parche
- evaluacion de modelos
- reproduccion o resintesis
- pruebas de muteo y energia acumulada

3. Pipeline de datos
- que se registra
- en que formato
- con que timestamps
- como se sincroniza video, Arduino y software host

4. Protocolo experimental minimo viable
- pasos concretos
- materiales
- costo aproximado
- numero minimo de pruebas
- criterios de exito y fracaso

5. Primer modelo implementable
- cual seria la primera version del modelo que vale la pena programar
- que variables de entrada usa
- que salidas controla
- que simplificaciones acepta

6. Roadmap de implementacion
- etapa 0: resguardo del software actual
- etapa 1: instrumentacion y logging
- etapa 2: dataset y calibracion
- etapa 3: primer modelo temporal/timbrico
- etapa 4: validacion con pruebas reales
- etapa 5: refinamientos y posibles sensores extra

7. Entregables de ingenieria
- estructura de carpetas o modulos
- pseudocodigo o codigo base sugerido
- archivos de configuracion
- tablas de parametros
- guias de testeo

8. Priorizacion costo-beneficio
- que hacer primero con lo que ya existe
- que compra puntual valdria la pena si realmente mejora mucho el sistema

Si es posible, quiero que cierres con una propuesta extremadamente concreta de "primer sprint" de 1 a 3 dias de trabajo, con objetivos medibles y sin depender de equipamiento caro.
