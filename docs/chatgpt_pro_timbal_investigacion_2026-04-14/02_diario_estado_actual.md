# Diario y estado actual del proyecto

## Referencia temporal
- El audio dice "hoy es 13".
- El archivo fue guardado el 2026-04-14.
- Tomo como referencia probable que el audio fue grabado el 2026-04-13.
- En esa interpretacion, el "lunes pasado" mencionado en el audio corresponde al 2026-04-06.

## Resumen ejecutivo
El problema principal ya no es solo latencia o volumen: el nucleo del trabajo paso a ser el modelado fisico y temporal del timbal digital, para que la respuesta a los golpes sea consistente, continua y verosimil.

El fallo mas serio detectado es una discontinuidad timbrica y dinamica: golpes de fuerza parecida pueden producir respuestas demasiado distintas, con saltos bruscos entre rangos medios y altos. Eso hace que el instrumento se perciba por momentos como si cambiara de tambor en vez de responder como un mismo parche real.

## Hechos registrados

### 1. Nuevo timbal recibido
- Llegada de una nueva version del timbal alrededor del 2026-04-06.
- La construccion general se percibe visualmente bien.
- Aparece ruido electrico o de conexion mayor al deseado.
- Ese ruido no se considera la prioridad actual.

### 2. Problema principal de respuesta
- El volumen del golpe no representa de manera confiable la fuerza ejecutada.
- El timbre cambia de forma abrupta entre rangos cercanos de intensidad.
- El salto entre golpes medios y medios-altos se siente artificial.
- La respuesta actual parece depender de un mapeo insuficiente de presion a timbre y dinamica.

### 3. Falta de naturalidad fisica
- No esta bien representada la relacion entre:
  - fuerza de impacto
  - duracion del contacto
  - rebote de la baqueta
  - apagado del parche
  - acumulacion de energia en golpes sucesivos
- Se sospecha que el algoritmo actual falla especialmente en la dimension temporal.

### 4. Muteo incompleto o defectuoso
- Hay parches nuevos sin boton de muteo conectado.
- Incluso con parches que si tienen boton, el comportamiento no parece consistente.
- Puede haber una combinacion de problema electronico y problema de software.
- Se pide:
  - agregar soporte claro al boton de muteo
  - permitir desactivar el muteo desde software para testeo
  - modelar un muteo que imite el contacto de la mano con el timbal real

### 5. Posible pedal compartiendo cable con el boton
- Se propone distinguir boton y pedal usando una misma linea electrica.
- La diferenciacion podria venir por duracion del pulso, frecuencia o forma temporal de la senal.
- Usos posibles del pedal:
  - muteo
  - cambio de set
  - cambio de tonalidad
  - experimentos futuros de glissando

### 6. Necesidad de calibracion y experimento
- El sistema podria requerir calibracion parche por parche.
- Se propone un experimento sincronizado con:
  - video superior para localizar el punto de impacto
  - video lateral para medir gesto y velocidad de entrada
  - grilla o patron visual de calibracion
  - captura de datos Arduino
  - captura de pantalla del software

## Hipotesis tecnicas actuales

### Hipotesis A
La informacion de los sensores alcanza para mejorar bastante, pero falta un modelo temporal y fisico mas rico entre entrada y salida.

### Hipotesis B
Los tres piezoelectricos actuales pueden ser insuficientes para inferir con precision variables como tiempo de contacto o distribucion espacial fina del golpe.

### Hipotesis C
La solucion probablemente no sea solo machine learning ni solo reglas manuales. Lo mas razonable es un sistema hibrido:
- sustrato fisico o heuristico basado en la fisica del timbal
- capa de calibracion y ajuste empirico
- posiblemente aprendizaje o ajuste supervisado para compensar lo que la teoria no capture

## Restricciones explicitadas
- No hay presupuesto ilimitado.
- Se prefiere trabajar con el hardware disponible.
- Si hace falta comprar algo, debe justificar multiples usos.
- Antes de hacer una gran implementacion, se quiere investigacion seria.

## Estado del software hoy
- La app host esta hecha en Python.
- Hay UI nueva y UI legacy.
- Ya existe un experimento host-side analogico para streamear senal cruda del Arduino.
- Ya existe tambien un roadmap de firmware orientado a latencia y robustez.
- Lo que falta ahora es una linea de trabajo especifica sobre modelado fisico, timbrico y temporal del timbal.

## Decision inmediata tomada en este paquete
Se prioriza preparar material de investigacion para ChatGPT Pro antes de tocar la arquitectura del software. El siguiente paso, despues de recibir esa investigacion, deberia ser decidir si conviene:
- duplicar el software actual y abrir una rama o version experimental
- o crear una herramienta paralela, mas pequena, dedicada solo a analisis y calibracion
