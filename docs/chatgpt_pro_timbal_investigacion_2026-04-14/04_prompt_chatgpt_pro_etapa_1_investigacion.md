Quiero que trabajes como investigador tecnico senior en modelado fisico de instrumentos de percusion y sistemas interactivos en tiempo real.

Te adjunto:
- un brief tecnico del proyecto
- un diario con el estado actual y los problemas observados
- un roadmap de firmware ya existente
- una nota sobre un experimento host-side analogico ya implementado
- opcionalmente una transcripcion mas larga del audio de trabajo

Necesito que hagas una investigacion profunda y rigurosa sobre como modelar un timbal digital experimental cuyo objetivo no es solo detectar golpes, sino reproducir de manera creible el comportamiento fisico y timbrico del timbal.

Contexto minimo:
- hay Arduino y software host en Python
- el sensado actual usa tres piezoelectricos en paralelo
- el problema principal no es solamente latencia
- el problema central es el modelado de la relacion entre golpe, energia, timbre, decay, rebote, muteo y acumulacion de energia
- hoy la respuesta tiene saltos artificiales de timbre y dinamica
- tambien hay que decidir si el hardware actual alcanza o si hace falta alguna mejora puntual de bajo costo

Necesito que respondas con mucha exigencia tecnica. No quiero una respuesta simplificada ni motivacional. Quiero que distingas con claridad:
- que cosas estan respaldadas por fisica o literatura conocida
- que cosas son inferencias tuyas
- que cosas serian heuristicas razonables si no hubiera modelo completo

Puntos que quiero que investigues:

1. Como se puede modelar fisicamente un timbal o una membrana tensada comparable para este caso de uso.
2. Que variables minimas deberian entrar en el modelo para capturar de forma util:
   - fuerza del golpe
   - posicion del golpe
   - duracion del contacto
   - rebote de la baqueta
   - muteo por contacto
   - acumulacion de energia entre golpes sucesivos
   - transicion timbrica entre golpe corto, golpe retenido y golpe con presion residual
3. Si con tres piezoelectricos en paralelo y Arduino hay informacion suficiente para aproximar ese comportamiento o si hay limites duros.
4. Que tipo de enfoque conviene mas en este contexto:
   - modelo fisico reducido
   - reglas heuristicas temporales
   - calibracion empirica
   - machine learning
   - identificacion de sistemas
   - combinaciones hibridas
5. Que experimentos de bajo costo conviene hacer para obtener datos utiles y calibrar el modelo.
6. Como estructurar un dataset sincronizado entre gesto, sensores y salida sonora.
7. Que arquitectura de software experimental recomendarias para investigar esto sin destruir el software actual.

Formato obligatorio de la respuesta:

1. Diagnostico tecnico del problema.
2. Modelo fisico o cuasi-fisico propuesto.
3. Evaluacion del hardware actual y limites observables.
4. Estrategia de modelado recomendada, con comparacion de alternativas.
5. Experimentos concretos de bajo costo.
6. Arquitectura experimental de software y pipeline de datos.
7. Roadmap priorizado en etapas.
8. Riesgos, supuestos y preguntas abiertas.
9. Referencias y fuentes.

Pautas de calidad:
- Si propones ecuaciones, explicalas y deci para que sirven en la practica.
- Si propones machine learning, justifica por que seria mejor que una heuristica fisica simple.
- Si el hardware actual no alcanza para cierto objetivo, decilo sin suavizarlo.
- Priorizo soluciones operables en tiempo real y con presupuesto limitado.
- Quiero una respuesta con densidad tecnica alta.
