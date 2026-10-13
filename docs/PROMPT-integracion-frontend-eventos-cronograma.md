# Prompt — Integración Frontend: Eventos en tarjetas + Cronograma (Church Connect)

> Copia este bloque completo y pásalo a tu asistente de código (o úsalo como especificación de la tarea).
> Describe las novedades del contrato del backend `Church-Connect-backend` (FastAPI) sobre los
> módulos **Events** y **Schedules**, que ya existen como CRUD completo en
> `Church-Connect-Frontend`. Este documento **no es una integración desde cero**: es un delta
> sobre lo ya implementado (`EventsListPage`, `EventDetailPage`, `SchedulesListPage`,
> `ScheduleForm`, etc.), para soportar la vista de eventos en tarjetas, el modal de "añadir
> cronograma" con validación de rango/solape, y la línea de tiempo para el usuario final.
>
> **Depende de** `docs/PROMPT-integracion-frontend-auth-users.md` (httpClient, envelope,
> token) — sin cambios ahí.

---

## 1. Qué cambió en `EventResponse`

Nuevo campo, de solo lectura (no se envía en `EventCreate`/`EventUpdate`):

| Campo | Tipo | Notas |
|---|---|---|
| `total_actividades` | `number` | Cantidad de cronogramas (`ScheduleResponse`) asociados a ese evento. `0` si no tiene ninguno. Se recalcula en cada `GET /events`, `GET /events/{id}`, `POST /events` y `PUT /events/{id}`. |

Úsalo en la tarjeta de evento para el indicador "Cronograma: N actividades" / "Sin cronograma"
(criterio de aceptación 1.2 / 2.5), en vez de hacer un `GET /schedules?evento_id=...` extra por
cada tarjeta.

## 2. Qué cambió en `ScheduleResponse` / `ScheduleCreate` / `ScheduleUpdate`

Nuevo campo `descripcion`:

| Campo | Tipo | Notas |
|---|---|---|
| `descripcion` | `string \| null` | Texto libre opcional, descripción de la actividad del cronograma (distinto de `actividad`, que es el título). `null`/omitido si no se envía. |

El resto de los campos (`actividad`, `hora_inicio`, `hora_fin`, `responsable`, `evento_id`) no
cambian.

## 3. Nuevas validaciones de negocio en `POST /schedules` y `PUT /schedules/{id}`

Antes solo se validaba `hora_fin > hora_inicio`. Ahora el backend también valida:

1. **Rango dentro del evento**: `hora_inicio >= evento.fecha_inicio` y
   `hora_fin <= evento.fecha_fin`. Si no se cumple, `400` con mensaje
   `"El cronograma debe estar dentro del rango de fechas del evento"`.
2. **Sin solapes**: la actividad no puede solaparse en el tiempo con ninguna otra actividad
   existente del **mismo evento** (en `PUT`, se excluye la propia actividad que se está
   editando). Si se solapa, `400` con mensaje
   `"El horario se solapa con otra actividad del cronograma de este evento"`.

Estas reglas son la fuente de verdad; el frontend debe restringir los selectores de hora al
rango del evento (p. ej. `min`/`max` en un `<input type="datetime-local">`) y validar
localmente para dar feedback inmediato, pero **siempre debe manejar el `400` del backend**
como respaldo (p. ej. condiciones de carrera entre dos admins editando el mismo evento a la vez).

No hay endpoint batch: cada actividad del cronograma se crea/edita/borra con una llamada
independiente a `POST`/`PUT`/`DELETE /schedules`. Si el formulario del frontend permite agregar
varias actividades a la vez antes de "Guardar", debe enviarlas con llamadas independientes
(p. ej. `Promise.allSettled`) y reportar errores por fila si alguna falla, sin descartar las que
sí se guardaron.

## 4. Sin cambios

- Rutas, prefijos, roles (`GET` abierto a cualquier autenticado, escritura solo `ADMIN`) y el
  envelope `ResponsePayload` siguen igual.
- `evento_id` sigue sin ser editable en `PUT /schedules/{id}`.
- `DELETE /events/{id}` sigue devolviendo `409` si el evento tiene cronogramas asociados.
