# Problema: Impresora térmica no imprime (Bixolon SRP-F310 / F312 / F312II)

## Categoría
- impresora_termica

## Síntomas
- La impresora **no saca el recibo** ni responde al comando de impresión.
- La luz de **POWER** está encendida, pero **no sale papel**.
- Se escucha el motor intentar imprimir, pero la hoja no avanza.
- No aparecen códigos de error visibles.

## Causas probables
- Papel mal colocado o agotado.
- Tapa superior mal cerrada.
- Obstrucción en la salida del papel.
- Impresora fuera de línea o puerto incorrecto.
- Fallo de comunicación con la PC o caja registradora.

## Pasos de solución

1. **Verificar estado de la impresora**
   - Confirmar que el LED de **POWER** esté encendido.
   - Si la luz de **ERROR** está fija o parpadeando, revisar tapa y papel.

2. **Comprobar el papel térmico**
   - Abrir la tapa superior con el botón de liberación.
   - Verificar que haya papel suficiente.
   - El papel térmico debe colocarse con el lado **brillante** hacia abajo (el que marca).
   - Asegurarse de que el rollo esté centrado y no trabado.

3. **Cerrar correctamente la tapa**
   - Cerrar la tapa superior hasta escuchar un **clic**.
   - Si la tapa queda floja, la impresora no imprimirá.

4. **Imprimir un auto-test desde la impresora**
   - Apagar la impresora.
   - Mantener presionado el botón **FEED** y encenderla.
   - Debería imprimir una página interna de prueba.
   - Si **no imprime el auto-test**, el problema es de hardware.

5. **Revisar conexión con la PC/Caja**
   - Verificar que el cable **USB / Serial / Ethernet** esté bien conectado.
   - Si la tienda usa Ethernet, confirmar que el cable esté en el puerto correcto del switch.
   - En caja registradora, confirmar que la impresora seleccionada es la correcta.

6. **Probar imprimir un recibo corto**
   - Intentar imprimir desde el sistema corporativo.
   - Si no responde, reiniciar la PC o caja e intentarlo de nuevo.

## Cuándo escalar
- La impresora **no imprime ni siquiera el auto-test**.
- El LED de **ERROR** permanece encendido después de revisar el papel.
- El motor hace ruido pero el papel no avanza.
- Olor a quemado o temperatura excesiva en la impresora.
- Escalar para:
  - Revisión del rodillo térmico.
  - Diagnóstico de motor o sensores.
  - Reemplazo de la impresora.

## Recursos visuales
![imagen referencia](https://storage.googleapis.com/multimedia_bot/impresora_termica.jpeg)