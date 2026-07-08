## ADDED Requirements

### Requirement: Espejo de recordatorios en Google Calendar
El sistema SHALL crear, tras la confirmación de un recordatorio y si la integración está configurada, un evento espejo en Google Calendar con el texto como título, la fecha/hora del recordatorio y la regla RRULE si es recurrente, guardando el identificador del evento junto al recordatorio.

#### Scenario: Recordatorio único espejado
- **WHEN** el usuario confirma un recordatorio único y la integración con Google Calendar está configurada
- **THEN** se crea un evento en el calendario con ese título y fecha/hora, y su id queda asociado al recordatorio

#### Scenario: Recordatorio recurrente espejado
- **WHEN** el usuario confirma un recordatorio recurrente y la integración está configurada
- **THEN** se crea un evento recurrente en el calendario con la misma regla de repetición

#### Scenario: Cancelación elimina el evento espejo
- **WHEN** el usuario cancela un recordatorio que tiene evento espejo
- **THEN** el sistema elimina el evento correspondiente de Google Calendar

### Requirement: El espejo nunca bloquea al recordatorio
El sistema SHALL tratar toda falla del espejo (API caída, token inválido o ausente) como no fatal: el recordatorio se guarda y dispara con normalidad, y el fallo del espejo se informa al usuario de forma breve.

#### Scenario: Falla la creación del evento
- **WHEN** la llamada a Google Calendar falla al confirmar un recordatorio
- **THEN** el recordatorio queda guardado y programado igualmente, y el bot avisa que no pudo reflejarlo en el calendario

#### Scenario: Integración no configurada
- **WHEN** no existe token de Google en el volumen de datos
- **THEN** el bot funciona completo sin intentar llamadas a Google Calendar ni mostrar errores

### Requirement: Autenticación con refresh token permanente
El sistema SHALL autenticarse contra Google Calendar usando credenciales OAuth de aplicación de escritorio y un token con refresh token generado una única vez fuera de la Pi, renovando el acceso automáticamente sin intervención del usuario.

#### Scenario: Renovación automática de acceso
- **WHEN** el access token expiró y el bot necesita llamar a la API
- **THEN** el bot renueva el acceso con el refresh token de forma transparente

#### Scenario: Refresh token revocado
- **WHEN** la renovación falla porque el refresh token fue revocado o venció
- **THEN** el bot desactiva el espejo, avisa al usuario una única vez que debe rehacer el login de Google, y sigue funcionando sin espejo
