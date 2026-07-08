## 1. Implementación

- [x] 1.1 `handlers.py`: `_mostrar_confirmacion` guarda `texto_origen` y `tarjeta` en `user_data["pendiente"]`; `_procesar_pedido` recibe el texto original para poder guardarlo
- [x] 1.2 `handlers.py`: `_procesar_pedido` arma el historial con precedencia hilo > pendiente (2 turnos derivados de `texto_origen`/`tarjeta`); ante "otro" con pendiente activo, la ayuda no toca el pendiente; ante aclaración, el hilo guardado parte del contexto del pendiente
- [x] 1.3 `nlp.py`: generalizar la regla de conversación previa del prompt (aclaración o propuesta pendiente; corrección devuelve el recordatorio completo conservando campos no mencionados)

## 2. Verificación

- [x] 2.1 Extender el smoke test con dobles: corrección parcial produce tarjeta nueva (y el pendiente viejo se reemplaza); mensaje sin relación deja el pendiente confirmable; corrección ambigua → aclaración → respuesta produce tarjeta; regresión de test_hilo y test_fase1
- [ ] 2.2 Probar en real (Pi): reproducir la conversación del 2026-07-08 («enviar mail el viernes» → tarjeta → «en vez de a las 9 que sea a las 10») y verificar que sale la tarjeta corregida
