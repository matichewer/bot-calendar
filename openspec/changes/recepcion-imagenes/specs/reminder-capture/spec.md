# reminder-capture Specification (delta)

## MODIFIED Requirements

### Requirement: Confirmación obligatoria antes de guardar
El sistema SHALL presentar toda interpretación como una tarjeta de confirmación con botones inline (confirmar y cancelar) mostrando el texto interpretado, la fecha/hora formateada en español y la recurrencia si existe, y SHALL persistir el recordatorio únicamente tras la confirmación explícita.

#### Scenario: Usuario confirma
- **WHEN** el usuario toca el botón de confirmar en la tarjeta
- **THEN** el sistema guarda el recordatorio, lo programa, y responde confirmando la creación

#### Scenario: Usuario cancela
- **WHEN** el usuario toca el botón de cancelar en la tarjeta
- **THEN** el sistema descarta la interpretación sin guardar nada y lo comunica

#### Scenario: Nuevo pedido con confirmación pendiente
- **WHEN** el usuario envía un nuevo pedido por texto o voz mientras hay una tarjeta de confirmación de texto/voz sin responder
- **THEN** el sistema descarta la interpretación pendiente de texto/voz y presenta la tarjeta del nuevo pedido, dejando intactas las tarjetas de confirmación originadas en imágenes (ver `image-event-capture`)
