## Context

El parseo NL es stateless: `nlp.interpretar(texto)` solo ve el último mensaje. El flujo de aclaración (spec `reminder-capture`) pregunta pero no registra que espera respuesta, así que la respuesta cae en la rama "otro" y muestra la ayuda. Ya existe un mecanismo análogo de estado conversacional efímero: la confirmación pendiente en `context.user_data`.

## Goals / Non-Goals

**Goals:**
- Que la respuesta a una aclaración (por texto o voz) se combine con el pedido original y produzca la tarjeta de confirmación.
- Soportar más de una ronda de aclaración con historial acumulado.
- Descartar el hilo limpiamente cuando la respuesta no viene al caso.

**Non-Goals:**
- Memoria de conversación general o persistente (chit-chat, referencias a recordatorios pasados).
- Sobrevivir reinicios: el hilo es efímero como la confirmación pendiente (trade-off ya aceptado en D6 del cambio original).

## Decisions

### D1. Historial en `user_data["hilo"]`, mismo patrón que la confirmación pendiente
Al responder con una aclaración, se guarda `user_data["hilo"]`: lista de turnos `{role, content}` con el pedido original (user) y la pregunta (assistant). El próximo mensaje se interpreta pasando ese historial; el LLM recibe la conversación real en formato multi-turn (no un texto concatenado), que es como mejor resuelven estos modelos. Alternativa considerada: re-armar un único string "pedido + respuesta"; descartada por frágil con múltiples rondas.

### D2. Tope de 6 turnos y limpieza explícita
El hilo se limpia cuando: (a) la interpretación produce una tarjeta de confirmación, (b) el LLM clasifica la respuesta como "otro" (no venía al caso), o (c) el historial supera 6 turnos (se descarta el más viejo par). Evita hilos zombis que contaminen pedidos futuros.

### D3. Instrucción explícita en el prompt
Se agrega al prompt del sistema: si hay conversación previa, la respuesta del usuario completa el pedido original; combinarlos. Sin esto, el modelo a veces trata el último mensaje como pedido nuevo.

## Risks / Trade-offs

- [El LLM combina mal las piezas] → La tarjeta de confirmación sigue siendo obligatoria; el error cuesta un tap.
- [Hilo activo y el usuario cambia de tema] → La clasificación "otro" descarta el hilo; a lo sumo ve la ayuda una vez, comportamiento actual.
- [Reinicio a mitad de aclaración] → Se pierde el hilo; el usuario repite el pedido completo. Igual que las confirmaciones pendientes.
