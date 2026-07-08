## ADDED Requirements

### Requirement: Continuidad de conversación tras una aclaración
Cuando el sistema hace una pregunta de aclaración, SHALL recordar el pedido original y la pregunta hecha, e interpretar el siguiente mensaje del usuario (texto o voz) junto con ese contexto, combinando las piezas en un único pedido. El hilo SHALL descartarse al presentar la tarjeta de confirmación, al detectar que la respuesta no se relaciona con la aclaración, o al reiniciarse el bot.

#### Scenario: Respuesta a la aclaración completa el pedido
- **WHEN** el bot preguntó «¿Cuándo querés que te recuerde comprar leche?» y el usuario responde «hoy a las 11:40»
- **THEN** el sistema interpreta el pedido combinado (texto="comprar leche", hoy 11:40) y presenta la tarjeta de confirmación

#### Scenario: Respuesta todavía ambigua extiende la conversación
- **WHEN** la respuesta a una aclaración sigue sin resolver el pedido (p. ej. «el jueves» sin hora)
- **THEN** el sistema hace una nueva pregunta de aclaración conservando el historial acumulado

#### Scenario: Respuesta sin relación descarta el hilo
- **WHEN** hay una aclaración pendiente y el usuario envía algo sin relación con ella ni con un recordatorio
- **THEN** el sistema descarta el hilo y trata el mensaje como uno nuevo
