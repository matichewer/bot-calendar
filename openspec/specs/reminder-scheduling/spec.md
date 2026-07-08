# reminder-scheduling Specification

## Purpose
Persistencia, programación y disparo de recordatorios por Telegram, incluyendo recurrencia, recuperación tras reinicios y gestión de recordatorios existentes.

## Requirements

### Requirement: Persistencia de recordatorios
El sistema SHALL persistir cada recordatorio confirmado en SQLite, en un volumen que sobrevive al ciclo de vida del contenedor, almacenando texto, próxima ejecución en ISO 8601 con zona horaria, regla de recurrencia opcional (formato RRULE) y estado.

#### Scenario: Recordatorio confirmado se persiste
- **WHEN** el usuario confirma un recordatorio
- **THEN** el recordatorio queda guardado en la base con estado activo antes de que se responda la confirmación

### Requirement: Disparo puntual por Telegram
El sistema SHALL enviar el mensaje del recordatorio por Telegram al chat autorizado en la fecha/hora programada.

#### Scenario: Recordatorio único se dispara
- **WHEN** llega la fecha/hora de un recordatorio único activo
- **THEN** el bot envía un mensaje por Telegram con el texto del recordatorio y lo marca como completado

#### Scenario: Recordatorio recurrente se dispara y reprograma
- **WHEN** llega la fecha/hora de un recordatorio recurrente activo
- **THEN** el bot envía el mensaje, calcula la siguiente ocurrencia según la regla de recurrencia y actualiza la próxima ejecución, manteniendo el recordatorio activo

### Requirement: Recuperación tras reinicio
El sistema SHALL reconstruir su agenda al arrancar leyendo todos los recordatorios activos de la base, reprogramándolos, y SHALL enviar inmediatamente los que vencieron mientras estaba apagado, marcados como atrasados.

#### Scenario: Reinicio sin recordatorios vencidos
- **WHEN** el bot arranca y todos los recordatorios activos tienen próxima ejecución futura
- **THEN** todos quedan programados y se disparan a su hora normalmente

#### Scenario: Reinicio con recordatorio vencido
- **WHEN** el bot arranca y un recordatorio único venció durante el apagado
- **THEN** el bot lo envía de inmediato indicando que está atrasado y lo marca como completado

#### Scenario: Reinicio con recurrente vencido
- **WHEN** el bot arranca y un recordatorio recurrente tiene ocurrencias vencidas durante el apagado
- **THEN** el bot envía un único aviso atrasado y reprograma el recordatorio a su próxima ocurrencia futura

### Requirement: Gestión de recordatorios existentes
El sistema SHALL ofrecer un comando `/lista` que muestre los recordatorios activos con su próxima ejecución y recurrencia, y SHALL permitir cancelar cualquiera de ellos mediante botones inline.

#### Scenario: Listar recordatorios activos
- **WHEN** el usuario envía `/lista`
- **THEN** el bot muestra cada recordatorio activo con texto, próxima fecha/hora y regla de repetición si la hay, o un mensaje de lista vacía

#### Scenario: Cancelar un recordatorio
- **WHEN** el usuario cancela un recordatorio desde la lista
- **THEN** el recordatorio pasa a estado cancelado, se desprograma y no vuelve a dispararse
