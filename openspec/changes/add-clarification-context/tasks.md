## 1. Implementación

- [x] 1.1 `nlp.py`: `interpretar()` acepta un historial opcional de turnos previos y lo envía al LLM como conversación multi-turn; agregar al prompt la instrucción de combinar la respuesta con el pedido original
- [x] 1.2 `handlers.py`: al responder con una aclaración, guardar el hilo (pedido original + pregunta) en `user_data`; al procesar un mensaje con hilo activo, pasarlo a `interpretar()`; limpiar el hilo al confirmar, ante clasificación "otro", y con tope de 6 turnos

## 2. Verificación

- [x] 2.1 Extender el smoke test con dobles: aclaración → respuesta corta produce tarjeta; respuesta aún ambigua re-pregunta conservando historial; respuesta sin relación limpia el hilo
- [ ] 2.2 Probar en real (Pi o PC): reproducir la conversación del bug («recordame comprar leche» → «hoy a las 11:40») y verificar que sale la tarjeta
