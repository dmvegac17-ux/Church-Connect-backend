# Inscripciones, aforo y participación sin rol

Contrato del backend para el rediseño de dos roles. Las pruebas que lo respaldan
están en `tests/test_inscripciones_aforo.py` y `tests/test_participaciones.py`.

## Roles

Solo existen `ADMIN` y `MEMBER`. «Participante» es la situación de quien está
asignado a una actividad (`cronogramas.responsable_id`), no un rol:

- Cualquier usuario activo puede ser asignado, también un administrador.
- Todos pueden ver y responder **sus propias** invitaciones
  (`/participante/invitaciones`). Lo que protege cada invitación es su dueño.
- La migración `e5f6a7b8c9d0` convierte los usuarios `PARTICIPANT` en `MEMBER`.
  Un `rol = "PARTICIPANT"` en el cuerpo de una petición responde `422`.

## Reglas de aforo

| Dato | Cálculo |
|---|---|
| Participantes | personas distintas con una actividad asignada (invitación pendiente o aceptada). Cuentan una vez aunque tengan varias actividades |
| Cupo para público | `capacidad` − participantes |
| Disponibles | cupo para público − inscripciones |
| Sobrecupo | participantes + inscripciones > `capacidad` |

Decisiones:

1. **Un participante no se inscribe**: ya ocupa su lugar (`409 es_participante`).
2. **Asignar a un inscrito** elimina su inscripción en la misma transacción; el
   aforo ocupado no cambia. La invitación queda con `reemplazo_inscripcion = true`.
3. **Quien rechaza, vence o es revocado** deja de ocupar aforo. No se le inscribe
   solo: puede inscribirse si quedan cupos.
4. **Asignar con el evento lleno se permite** y deja sobrecupo. No se borra público.
5. **El aforo no puede bajar de lo ocupado** (`409`, `data.campo = "capacidad"`).
6. **Las inscripciones cierran cuando el evento empieza** (`409 inscripciones_cerradas`).

El cupo se valida con la fila del evento bloqueada (`SELECT … FOR UPDATE`), igual
que la asignación de participantes y el cambio de `capacidad`: tres operaciones
simultáneas sobre el mismo evento se ordenan entre sí.

## `GET /events` y `GET /events/{id}` — campo `aforo`

| Campo | ADMIN | MEMBER |
|---|---|---|
| `capacidad` | aforo total | **cupo para público** (nunca el total) |
| `aforo.cupo_publico`, `aforo.disponibles` | ✅ | ✅ |
| `aforo.participantes`, `publico`, `ocupados`, `sobrecupo` | ✅ | `null` |
| `aforo.inscrito`, `inscripcion_id`, `participa` | de quien consulta | de quien consulta |
| `aforo.inscripcion_reemplazada` | su participación reemplazó una inscripción | ídem |
| `aforo.inscripciones_cerradas` | el evento ya empezó | ídem |

`aforo.disponibles` nunca es negativo; el exceso va en `aforo.sobrecupo`.

## `/registrations`

| Método | Quién | Qué hace |
|---|---|---|
| `POST` `{evento_id}` | cualquiera | Se inscribe. Devuelve `cupos_disponibles` |
| `POST` `{evento_id, usuario_id, nota?}` | ADMIN | Inscribe a otra persona (`inscrito_por` = el administrador). `403` para un miembro |
| `GET ?evento_id=` | ADMIN | Público del evento, con `usuario` e `inscrito_por_usuario` |
| `GET /me` | cualquiera | Sus inscripciones |
| `PATCH /{id}` `{nota}` | ADMIN | Edita la nota (máx. 200; vacía = `null`) |
| `DELETE /{id}` | dueño o ADMIN | Libera el cupo. El dueño no puede si el evento ya empezó |

Un `409` trae `data.codigo`: `sin_cupos`, `ya_inscrito`, `es_participante` o
`inscripciones_cerradas`.

## Autoasignación

`POST /admin/participaciones`, `…/reasignar` y `…/revocar` aceptan que
`participante_id` sea el propio administrador:

- La invitación nace `aceptada`, con `estado_envio = "autoasignada"`,
  `fecha_respuesta` = ahora y sin `fecha_limite_respuesta`.
- No se envía correo ni se crea notificación. `dias_para_confirmar` se ignora
  (y es obligatorio para cualquier otra persona: `422` si falta).
- `acciones_permitidas` solo trae `revocar_y_cambiar`.
- Si el administrador revoca **su propia** asignación para dársela a otro, no se
  le notifica: `notificacion_revocacion_estado` queda en `null`.

`GET /participante/invitaciones` añade `autoasignada`;
`GET /admin/participantes/elegibles` devuelve a todos los usuarios activos y añade
`inscrito` y `participa` para avisar antes de asignar.

## Notificaciones

`DELETE /notificaciones/{id}`: el administrador elimina cualquiera; el resto,
solo las propias (`403` si es de otra persona).

## Eventos finalizados

Un evento cuya `fecha_fin` ya pasó queda como registro. Uno en curso todavía no
cuenta como finalizado.

| Operación sobre un evento finalizado | Resultado |
|---|---|
| `PUT /events/{id}` (cualquier campo) | `409` |
| `POST /schedules`, `PUT /schedules/{id}`, `DELETE /schedules/{id}` | `409` |
| `POST /admin/participaciones`, `…/reasignar`, `…/revocar` (también autoasignarse) | `409` |
| `POST /registrations` | `409 inscripciones_cerradas` (cierran al empezar) |
| Cualquier `GET` | sin cambios |
| `DELETE /events/{id}` | permitido; se lleva su cronograma, invitaciones e inscripciones |

Los `409` de las tres primeras filas traen `data.codigo = "evento_finalizado"`.
La regla vive en `src/core/exceptions/custom_exceptions.py` (`EventoFinalizadoError`
y `evento_finalizado`) y se traduce a HTTP en un único manejador.

Las inscripciones de un evento finalizado sí se pueden seguir depurando por el
administrador (editar la nota o eliminar una).

## Límites de inscripción

Dos campos opcionales del evento (migración `f6a7b8c9d0e1`):

| Campo | Qué hace | Sin valor |
|---|---|---|
| `fecha_limite_inscripcion` | Hasta cuándo se inscribe el público. No puede ser posterior a `fecha_inicio` (`400`) | Hasta que el evento empiece |
| `dias_limite_cancelacion` (0–365) | Días antes del inicio en que se cierra la cancelación de la propia inscripción | Hasta que el evento empiece |

- Son límites **para el público**. Un administrador inscribe o retira a
  alguien hasta que el evento empieza.
- `POST /registrations` fuera de plazo → `409 inscripciones_cerradas`.
- `DELETE /registrations/{id}` del dueño fuera de plazo → `409 cancelacion_cerrada`.
- El evento devuelve `fecha_limite_cancelacion` (calculada) y, en `aforo`,
  `inscripciones_cerradas` y `cancelacion_cerrada` según quien consulta.
- Cerrar inscripciones no cierra la cancelación, ni al revés.
- Cambiar estos límites no avisa a los inscritos.

La regla vive en `src/application/events/registration_window.py`.

## Horarios del cronograma en bloque

`PUT /schedules/horarios` `{evento_id, items: [{id, hora_inicio, hora_fin}]}`
(solo `admin`) cambia de una vez el horario de varias actividades. Valida cómo
queda el cronograma completo —dentro del evento y sin solapamientos— y guarda
todo o nada. Existe porque reordenar intercambia horarios: guardando de a una,
la primera chocaría con la que todavía ocupa su hueco.
