# Tasks: recepción de imágenes con detección de eventos

## 1. Configuración

- [x] 1.1 Agregar `groq_vision_model` a `Config` en `bot/config.py`, leído de `GROQ_VISION_MODEL` con default `meta-llama/llama-4-scout-17b-16e-instruct`
- [x] 1.2 Documentar `GROQ_VISION_MODEL` en `.env.example` (opcional, con el default y la alternativa Maverick comentada)

## 2. Interpretación de imágenes (nlp.py)

- [x] 2.1 Escribir `PROMPT_VISION`: extracción de un array JSON de eventos (`mensaje`, `fecha_hora_iso`, `recurrencia_rrule`) más clave `omitidos`, con las mismas convenciones del prompt de texto (zona horaria, no inventar, defaults de franja horaria), regla de 09:00 para eventos sin hora, próxima ocurrencia futura si falta el año, y cap de 10 eventos
- [x] 2.2 Implementar `NLP.interpretar_imagen(imagen: bytes, caption: str | None) -> tuple[list[Interpretacion], list[str]]`: data URL base64 en turno `user` multimodal junto con el prompt y el contexto de fecha actual, sin `response_format`, lanzando `NLPError` ante fallas de API
- [x] 2.3 Implementar parseo tolerante de la respuesta (extraer el primer bloque JSON del texto; si no hay, tratar como 0 eventos) y validar cada evento reusando `_validar`, descartando los inválidos hacia la lista de omitidos sin abortar el resto

## 3. Estado pendiente múltiple y confirmación (handlers.py)

- [x] 3.1 Extraer el camino de persistencia de `callback_confirmacion` a un helper `_confirmar_propuesta` (db.crear + scheduler.programar + gcal.crear_evento + armado de las líneas de respuesta), y verificar que el flujo de texto sigue funcionando igual
- [x] 3.2 Generalizar `callback_confirmacion`: resolver el token primero contra `user_data["pendiente"]` (comportamiento actual intacto) y después contra `user_data["pendientes_imagen"]`; confirmar/cancelar afecta solo esa entrada; token desconocido responde «ya no está vigente»
- [x] 3.3 Implementar el armado de tarjetas de imagen: token por evento, tarjeta con el mismo formato que las de texto, registro en `pendientes_imagen` con `msg_id`

## 4. Handler de fotos

- [x] 4.1 Implementar `handlers.foto`: ChatAction, descarga de `photo[-1]`, llamada a `interpretar_imagen` con el caption, y manejo de `NLPError` con `MENSAJE_SIN_SERVICIO`
- [x] 4.2 Al recibir una foto nueva, marcar como reemplazadas las tarjetas de imagen anteriores no respondidas (editar sus mensajes) y limpiar `pendientes_imagen`
- [x] 4.3 Componer las respuestas: aviso si no hay eventos, mensaje introductorio con la cantidad encontrada, una tarjeta por evento, y línea final con los omitidos si los hay
- [x] 4.4 Registrar `MessageHandler(filters.PHOTO, handlers.foto)` en `bot/main.py` y actualizar el texto de `AYUDA` mencionando que se pueden mandar fotos

## 5. Verificación

- [ ] 5.1 Probar de punta a punta con el bot corriendo: foto de invitación (1 evento), foto de cronograma (varios eventos, confirmación parcial), foto sin eventos, y verificar que un pedido de texto no mata las tarjetas de imagen y que una foto nueva sí las reemplaza
- [x] 5.2 Verificar la degradación: `GROQ_API_KEY` inválida o modelo inexistente → mensaje de servicio caído, recordatorios existentes intactos
- [ ] 5.3 Verificar que los eventos confirmados desde una imagen aparecen en `/lista` y en Google Calendar igual que los de texto
