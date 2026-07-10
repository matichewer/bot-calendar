# image-event-capture Specification (delta)

## ADDED Requirements

### Requirement: Interpretación de imágenes con eventos
El sistema SHALL aceptar fotos enviadas por Telegram e interpretarlas con un modelo de visión configurable, extrayendo una lista de eventos (texto a recordar, fecha/hora en la zona horaria configurada, recurrencia opcional), usando la fecha/hora actual como referencia y el caption de la foto —si existe— como contexto adicional. El sistema SHALL NOT inventar fechas: un evento cuya fecha no sea deducible de la imagen se omite y se informa.

#### Scenario: Invitación con un evento
- **WHEN** el usuario envía la foto de una invitación de cumpleaños con fecha y hora legibles
- **THEN** el sistema presenta una tarjeta de confirmación con el evento (descripción, fecha y hora extraídas de la imagen)

#### Scenario: Cronograma con múltiples eventos
- **WHEN** el usuario envía la foto de un cronograma de exámenes con varias fechas
- **THEN** el sistema anuncia cuántos eventos encontró y presenta una tarjeta de confirmación independiente por cada uno, hasta un máximo de 10 por imagen

#### Scenario: Evento sin hora legible
- **WHEN** un evento detectado tiene fecha pero no hora deducible
- **THEN** el sistema propone las 09:00 como hora de aviso y la tarjeta muestra esa hora explícitamente

#### Scenario: Evento sin fecha deducible
- **WHEN** la imagen menciona un evento cuya fecha no puede deducirse
- **THEN** el sistema lo omite de las tarjetas y lo informa en una línea aparte, sin preguntar aclaraciones ni inventar datos

#### Scenario: Imagen sin eventos
- **WHEN** el usuario envía una foto sin fechas ni eventos reconocibles
- **THEN** el sistema responde que no encontró eventos en la imagen, sin crear nada

### Requirement: Confirmación individual por evento detectado
El sistema SHALL presentar cada evento detectado como una tarjeta de confirmación independiente con botones inline de confirmar y cancelar, y SHALL persistir, programar y espejar en Google Calendar únicamente los eventos confirmados explícitamente, por el mismo camino que un recordatorio de texto. Las tarjetas SHALL ser independientes entre sí: responder una no afecta a las demás.

#### Scenario: Confirmación parcial
- **WHEN** una imagen produjo tres tarjetas y el usuario confirma dos y cancela una
- **THEN** el sistema guarda y programa exactamente los dos eventos confirmados, descarta el cancelado, y cada tarjeta refleja su resultado

#### Scenario: Tarjetas de imagen sobreviven a pedidos de texto
- **WHEN** hay tarjetas de imagen sin responder y el usuario envía un pedido de recordatorio por texto o voz
- **THEN** las tarjetas de imagen siguen vigentes y confirmables después de procesarse el pedido de texto

#### Scenario: Una foto nueva reemplaza las tarjetas anteriores
- **WHEN** hay tarjetas de imagen sin responder y el usuario envía una nueva foto
- **THEN** el sistema marca las tarjetas anteriores como reemplazadas (dejan de ser confirmables) y presenta las de la nueva imagen

#### Scenario: Tarjeta ya no vigente
- **WHEN** el usuario toca un botón de una tarjeta reemplazada o ya respondida
- **THEN** el sistema informa que el pedido ya no está vigente, sin crear nada

### Requirement: Degradación ante fallas del modelo de visión
El sistema SHALL manejar fallas de la API de visión (errores, rate limit, timeout, respuesta no parseable) informando al usuario que no pudo procesar la imagen y que reintente, sin afectar los recordatorios ya guardados ni las tarjetas pendientes existentes.

#### Scenario: API de visión no disponible
- **WHEN** la llamada al modelo de visión falla al interpretar una foto
- **THEN** el sistema responde en español que no pudo procesar el pedido en este momento y los recordatorios existentes siguen funcionando

#### Scenario: Respuesta del modelo inutilizable
- **WHEN** el modelo de visión devuelve una salida de la que no puede extraerse ningún evento válido
- **THEN** el sistema lo trata como una imagen sin eventos y responde el aviso correspondiente, sin crear nada
