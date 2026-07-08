# reminder-capture Specification

## Purpose
Captura e interpretación de pedidos de recordatorio en español natural (texto y notas de voz) vía Telegram, con confirmación explícita antes de guardar.

## Requirements

### Requirement: Interpretación de pedidos en lenguaje natural por texto
El sistema SHALL interpretar mensajes de texto en español natural extrayendo el texto a recordar, la fecha/hora de aviso y la recurrencia opcional, usando la fecha/hora actual y la zona horaria configurada como referencia para expresiones relativas.

#### Scenario: Pedido único con fecha relativa
- **WHEN** el usuario envía "recordame llamar al médico mañana a las 10"
- **THEN** el sistema interpreta texto="llamar al médico", fecha/hora = mañana 10:00 en la zona horaria configurada, sin recurrencia, y presenta la tarjeta de confirmación

#### Scenario: Pedido recurrente
- **WHEN** el usuario envía "recordame sacar la basura todos los lunes a las 8"
- **THEN** el sistema interpreta texto="sacar la basura", recurrencia semanal los lunes 08:00, próxima ejecución el lunes siguiente, y la tarjeta de confirmación muestra explícitamente la regla de repetición

#### Scenario: Pedido ambiguo o incompleto
- **WHEN** el usuario envía un pedido al que le falta información esencial (p. ej. "recordame el cumpleaños de Ana" sin fecha)
- **THEN** el sistema NO inventa datos y responde con una pregunta de aclaración en español

#### Scenario: Mensaje que no es un pedido de recordatorio
- **WHEN** el usuario envía un mensaje sin intención de recordatorio (p. ej. "hola")
- **THEN** el sistema responde explicando brevemente qué sabe hacer, sin crear nada

### Requirement: Interpretación de pedidos por nota de voz
El sistema SHALL aceptar notas de voz de Telegram, transcribirlas a texto en español mediante la API de transcripción, y procesar el resultado por el mismo flujo de interpretación que los mensajes de texto.

#### Scenario: Nota de voz válida
- **WHEN** el usuario envía una nota de voz diciendo "recordame regar las plantas el viernes a las siete de la tarde"
- **THEN** el sistema transcribe el audio, interpreta el pedido y presenta la tarjeta de confirmación, idéntica a la que produciría el mismo pedido por texto

#### Scenario: Falla la transcripción
- **WHEN** la API de transcripción falla o devuelve texto vacío
- **THEN** el sistema informa que no pudo entender el audio y pide reintentarlo o escribirlo, sin crear nada

### Requirement: Confirmación obligatoria antes de guardar
El sistema SHALL presentar toda interpretación como una tarjeta de confirmación con botones inline (confirmar y cancelar) mostrando el texto interpretado, la fecha/hora formateada en español y la recurrencia si existe, y SHALL persistir el recordatorio únicamente tras la confirmación explícita.

#### Scenario: Usuario confirma
- **WHEN** el usuario toca el botón de confirmar en la tarjeta
- **THEN** el sistema guarda el recordatorio, lo programa, y responde confirmando la creación

#### Scenario: Usuario cancela
- **WHEN** el usuario toca el botón de cancelar en la tarjeta
- **THEN** el sistema descarta la interpretación sin guardar nada y lo comunica

#### Scenario: Nuevo pedido con confirmación pendiente
- **WHEN** el usuario envía un nuevo pedido mientras hay una tarjeta de confirmación sin responder
- **THEN** el sistema descarta la interpretación pendiente y presenta la tarjeta del nuevo pedido

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

### Requirement: Degradación ante fallas del servicio de interpretación
El sistema SHALL manejar fallas de la API del LLM (errores, rate limit, timeout) informando al usuario que no pudo interpretar el pedido y que reintente, sin afectar los recordatorios ya guardados.

#### Scenario: API de LLM no disponible
- **WHEN** la llamada al LLM falla al interpretar un pedido
- **THEN** el sistema responde en español que no pudo procesar el pedido en este momento, y los recordatorios existentes siguen disparándose con normalidad
