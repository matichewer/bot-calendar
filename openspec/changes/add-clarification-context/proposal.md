## Why

Cuando el bot hace una pregunta de aclaración («¿Cuándo querés que te recuerde comprar leche?»), la respuesta del usuario («Hoy a las 11:40») se interpreta aislada, sin contexto: no parece un pedido de recordatorio y el bot contesta con el texto de ayuda. Detectado en uso real el 2026-07-08. El flujo de aclaración que exige la spec queda inutilizable si el bot no recuerda qué preguntó.

## What Changes

- El bot mantiene el hilo de la conversación durante una aclaración: al preguntar, guarda el pedido original y la pregunta hecha; el siguiente mensaje (texto o voz) se interpreta junto con ese intercambio previo, para que el LLM combine las piezas.
- Si la respuesta sigue siendo ambigua, la conversación se extiende (nueva aclaración, historial acumulado, con tope).
- Si la respuesta no tiene relación con la aclaración, el hilo se descarta y el mensaje se trata como nuevo.
- El hilo también se descarta al mostrar la tarjeta de confirmación (el pedido ya está resuelto).

## Capabilities

### New Capabilities

(ninguna)

### Modified Capabilities

- `reminder-capture`: se agrega el requirement de continuidad de conversación tras una aclaración (las respuestas a una pregunta del bot se interpretan con el contexto del pedido original).

## Impact

- Código: `bot/nlp.py` (interpretar con historial de conversación, ajuste del prompt) y `bot/handlers.py` (guardar/limpiar la aclaración pendiente en `user_data`).
- Sin cambios de esquema de datos, dependencias ni despliegue. El estado del hilo es efímero (en memoria): un reinicio del bot lo pierde, igual que las confirmaciones pendientes.
