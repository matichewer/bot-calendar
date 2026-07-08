## Why

Cuando el bot ya mostró la tarjeta de confirmación y el usuario manda una corrección en lenguaje natural («en vez de a las 9 hacé que sea a las 10»), el bot no tiene contexto: el mensaje se interpreta solo, sale una aclaración genérica y el usuario tiene que cancelar y repetir todo. Ocurrió en uso real el 2026-07-08. El fix del hilo de aclaraciones (add-clarification-context) no cubre este caso: el hilo se limpia justo al mostrar la tarjeta.

## What Changes

- Al procesar un mensaje (texto o audio) mientras hay una tarjeta de confirmación pendiente, se le pasa al LLM el recordatorio pendiente como contexto de conversación.
- Si la interpretación resultante es un recordatorio completo, se muestra una tarjeta nueva que reemplaza a la pendiente (mecanismo de reemplazo ya existente: «↩️ Reemplazado por un pedido más nuevo»).
- Si el mensaje no tiene relación con recordatorios, se responde con la ayuda como hoy; la tarjeta pendiente queda intacta y sigue siendo confirmable.
- Sin comandos nuevos ni cambios de esquema: es una extensión del flujo de captura.

## Capabilities

### New Capabilities

(ninguna)

### Modified Capabilities

- `reminder-capture`: nuevo requirement — un mensaje recibido con una confirmación pendiente se interpreta con el pendiente como contexto, permitiendo corregirlo conversacionalmente en vez de cancelar y repetir.

## Impact

- `bot/handlers.py`: `_procesar_pedido` arma el contexto a partir de `user_data["pendiente"]` cuando existe.
- `bot/nlp.py`: sin cambios estructurales (ya acepta `historial`); a lo sumo un ajuste menor del prompt para el caso "corrección de un pedido pendiente".
- Sin cambios en db, scheduler, gcal ni dependencias.
