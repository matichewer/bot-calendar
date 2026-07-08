## Context

`_procesar_pedido` interpreta cada mensaje sin saber que hay una tarjeta de confirmación esperando. El pendiente vive en `user_data["pendiente"]` (token, mensaje, fecha_iso, rrule, msg_id) hasta que el usuario confirma, cancela o lo pisa con un pedido nuevo. El change `add-clarification-context` ya le dio a `NLP.interpretar()` un parámetro `historial` multi-turn; acá se reutiliza ese mismo mecanismo.

## Goals / Non-Goals

**Goals:**
- Corregir un recordatorio pendiente hablando («que sea a las 10», «mejor el jueves») en texto o audio.
- No romper el flujo existente: aclaraciones, reemplazo de tarjeta, confirmación por token.

**Non-Goals:**
- Editar recordatorios YA confirmados (para eso está /lista + crear de nuevo).
- Mantener más de un pendiente a la vez (sigue habiendo uno solo).
- Persistir el pendiente entre reinicios (se pierde, como hoy).

## Decisions

### D1 — Reutilizar `historial` en vez de una API nueva en NLP
Cuando hay pendiente y no hay hilo de aclaración activo, `_procesar_pedido` fabrica un historial de 2 turnos a partir del pendiente: el pedido original del usuario y el texto de la tarjeta que mostró el bot. Para eso `_mostrar_confirmacion` guarda en `pendiente` dos campos nuevos: `texto_origen` (lo que dijo el usuario) y `tarjeta` (el texto de la tarjeta). Alternativa descartada: un parámetro `pendiente=` separado en `interpretar()` — duplica lógica de armado de mensajes para el mismo efecto.

Ajuste tras las pruebas en real (2026-07-08, dos rondas): el LLM no extraía los campos de la tarjeta, y adjuntarlos como texto al turno del asistente tampoco alcanzó — según la redacción del usuario («No, a las 9 re temprano…») seguía perdiendo el «qué». El formato final es un tercer turno con rol `system` que trae los datos exactos (`mensaje`, `fecha_hora_iso`, `recurrencia_rrule`) y la instrucción imperativa de copiar esos valores y modificar solo lo pedido. Verificado contra Groq real con 5 redacciones de corrección distintas + control negativo (charla sin relación sigue clasificando "otro").

### D2 — Precedencia: hilo de aclaración > pendiente
Si hay un hilo de aclaración activo se usa ese (ya contiene la conversación más reciente). Si no, y hay pendiente, se usa el contexto derivado del pendiente. Si la corrección resulta ambigua y el LLM pide aclaración, el hilo que se guarda parte del contexto del pendiente, así la respuesta siguiente conserva todo. El tope `MAX_TURNOS_HILO = 6` sigue aplicando.

### D3 — El pendiente no se toca salvo reemplazo
Si la interpretación sale completa → tarjeta nueva, y el mecanismo existente de reemplazo marca la vieja («↩️ Reemplazado por un pedido más nuevo»). Si sale "otro" → ayuda, y el pendiente queda intacto y confirmable (a diferencia del hilo, que sí se limpia). Cancelar/confirmar siguen siendo los únicos que consumen el pendiente.

### D4 — Ajuste del prompt
La regla de conversación previa del prompt se generaliza: los mensajes previos pueden ser (a) una pregunta de aclaración tuya, o (b) una propuesta de recordatorio esperando confirmación. En el caso (b), si el usuario pide un cambio, hay que devolver el recordatorio COMPLETO corregido (los campos no mencionados se conservan de la propuesta); si pide algo nuevo sin relación con la propuesta pero que sí es un recordatorio, se interpreta como pedido nuevo.

### D5 — Anclar los días de semana en el contexto de fecha (fix relacionado)
En las mismas pruebas reales el LLM resolvió dos veces «el viernes» al día equivocado (sábado 11 en vez de viernes 10): falla la aritmética de calendario. El mensaje de contexto de `interpretar()` ahora lista los próximos 7 días con su día de semana («jueves 09/07, viernes 10/07, …»), así la resolución de fechas relativas es una búsqueda, no un cálculo. No cambia ningún requirement (la interpretación correcta ya estaba especificada); es un detalle de implementación.

## Risks / Trade-offs

- [El LLM podría alterar un campo que el usuario no pidió cambiar] → temperatura 0, la propuesta original va completa en el contexto, y la tarjeta de confirmación sigue siendo la barrera antes de guardar.
- [Un mensaje nuevo legítimo con pendiente activo pisa la tarjeta] → comportamiento pre-existente (un solo pendiente); la tarjeta vieja queda marcada como reemplazada, nada se guarda sin confirmar.
- [Pendiente y hilo se pierden al reiniciar] → aceptado ya en changes anteriores; el usuario reenvía.
