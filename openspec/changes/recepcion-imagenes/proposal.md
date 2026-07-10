# Recepción de imágenes con detección de eventos

## Why

Hoy el bot solo acepta pedidos por texto y nota de voz. Muchos eventos llegan como imagen —una invitación de cumpleaños, la foto del cronograma de exámenes de la facultad— y pasarlos a mano es justo la fricción que el bot existe para eliminar. Un modelo de visión de Groq puede extraer los eventos directamente de la foto a un costo marginal despreciable (~2–3× un mensaje de texto).

## What Changes

- El bot acepta fotos por Telegram y las interpreta con un modelo de visión de Groq (Llama 4 Scout por defecto, configurable vía `GROQ_VISION_MODEL`). El caption de la foto, si existe, se usa como contexto.
- Una imagen puede producir **múltiples eventos** (caso cronograma de exámenes). Cada evento detectado se presenta como una tarjeta de confirmación **independiente**, con sus propios botones ✅/❌.
- El estado de confirmaciones pendientes se generaliza: además de la propuesta única de texto/voz actual (que conserva su flujo de corrección conversacional), se agrega un conjunto de propuestas pendientes por token para las tarjetas de imagen.
- Un pedido nuevo por texto/voz sigue reemplazando la tarjeta de texto pendiente, pero **no** descarta las tarjetas de imagen sin responder.
- Cada evento confirmado se persiste, programa y espeja en Google Calendar por el mismo camino que un recordatorio de texto.
- Fallas del modelo de visión degradan igual que las del LLM de texto: aviso al usuario, sin afectar recordatorios guardados.

## Capabilities

### New Capabilities

- `image-event-capture`: recepción de fotos por Telegram, extracción de una lista de eventos con un modelo de visión (fecha/hora en la zona horaria configurada, sin inventar datos), y confirmación individual por evento con tarjetas independientes.

### Modified Capabilities

- `reminder-capture`: el escenario «Nuevo pedido con confirmación pendiente» se acota — el reemplazo aplica solo a la propuesta pendiente de texto/voz; las tarjetas de confirmación originadas en una imagen permanecen vigentes hasta que el usuario las responda o expiren.

## Impact

- **Código**: `bot/nlp.py` (nuevo método de interpretación de imágenes + prompt de visión), `bot/handlers.py` (handler de fotos, tarjetas múltiples, generalización del callback de confirmación), `bot/config.py` (`GROQ_VISION_MODEL`), `bot/main.py` (registro del `MessageHandler(filters.PHOTO)`), `.env.example`.
- **Dependencias**: ninguna nueva — se reusa el cliente `groq` existente; el modelo de visión es otra llamada a la misma API.
- **Sistemas**: sin cambios en DB, scheduler ni Google Calendar (los eventos confirmados entran por el flujo existente). Sin migraciones.
- **Costo**: una foto consume ~1.000–2.000 tokens de entrada en Groq (Scout ~US$0,11/M tokens): del orden de US$0,0002–0,0005 por imagen.
