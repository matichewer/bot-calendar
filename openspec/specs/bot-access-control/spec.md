# bot-access-control Specification

## Purpose
Control de acceso del bot: solo el chat autorizado configurado puede interactuar; todo lo demás se ignora en silencio.

## Requirements

### Requirement: Acceso restringido a un único chat autorizado
El sistema SHALL procesar únicamente los updates provenientes del chat ID configurado en `ALLOWED_CHAT_ID`, e ignorar en silencio (sin respuesta alguna) todo mensaje, nota de voz o interacción con botones proveniente de cualquier otro chat.

#### Scenario: Mensaje del usuario autorizado
- **WHEN** llega un mensaje desde el chat ID autorizado
- **THEN** el bot lo procesa con normalidad

#### Scenario: Mensaje de un desconocido
- **WHEN** llega cualquier update desde un chat ID distinto al autorizado
- **THEN** el bot no responde nada, no procesa el contenido y no crea ningún dato

#### Scenario: Configuración ausente
- **WHEN** el bot arranca sin `ALLOWED_CHAT_ID` configurado
- **THEN** el bot falla al iniciar con un mensaje de error claro, en lugar de quedar abierto a cualquier chat
