## ADDED Requirements

### Requirement: Corrección conversacional del recordatorio pendiente
Cuando existe una tarjeta de confirmación pendiente y llega un mensaje nuevo (texto o transcripción de audio), el bot SHALL interpretar el mensaje pasando al modelo el recordatorio pendiente como contexto de conversación, de modo que una corrección parcial («que sea a las 10») produzca el recordatorio completo corregido sin que el usuario repita el pedido entero.

#### Scenario: Corrección parcial de la tarjeta pendiente
- **WHEN** hay una tarjeta pendiente («enviar mail — viernes 09:00») y el usuario manda «en vez de a las 9 que sea a las 10»
- **THEN** el bot muestra una tarjeta nueva con «enviar mail — viernes 10:00», los campos no mencionados se conservan, y la tarjeta anterior queda marcada como reemplazada

#### Scenario: Mensaje sin relación no destruye el pendiente
- **WHEN** hay una tarjeta pendiente y el usuario manda un mensaje que no tiene relación con recordatorios
- **THEN** el bot responde con la ayuda y la tarjeta pendiente sigue vigente y confirmable

#### Scenario: Corrección ambigua conserva el contexto
- **WHEN** hay una tarjeta pendiente y el usuario manda una corrección ambigua que dispara una pregunta de aclaración
- **THEN** la respuesta siguiente del usuario se interpreta con el contexto del pendiente y de la aclaración, y produce la tarjeta corregida
