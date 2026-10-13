# PROMPT 1 (v2) — ADMINISTRADOR, MIEMBROS Y PARTICIPANTES: UX/UI + BACKEND DE CONFIRMACIÓN DE PARTICIPACIONES

## 1. Rol y objetivo

Actúa como Senior Product Designer, Frontend Engineer y Backend Engineer con experiencia en aplicaciones web con múltiples roles y permisos.

Implementa en el repositorio existente, a partir de los diseños de referencia adjuntos (5 pantallas):

1. **Administrador → página "Participaciones"**: tabla de supervisión de invitaciones, con banner de alertas, filtros, búsqueda y acciones (Reasignar, Cancelar invitación, Reenviar).
2. **Participante → página "Confirmar participaciones"**: tarjetas de invitaciones con acciones Aceptar / No puedo participar, y modal de rechazo con motivo.
3. **Miembro**: sin cambios visuales ni funcionales.

El trabajo incluye **frontend, API y base de datos**. No entregues solo una propuesta, un prototipo aislado ni recomendaciones. No reconstruyas la aplicación ni elimines funcionalidades existentes.

---

## 2. Paso 0 — Inspección obligatoria antes de modificar

Antes de escribir código, inspecciona y documenta brevemente:

- Stack, ORM, sistema de migraciones y convenciones de nombres (tablas, columnas, rutas, DTOs). **Adapta todos los nombres de este prompt a esas convenciones**; los nombres aquí son orientativos.
- Modelo actual de **roles y permisos**: cómo se define el rol miembro, dónde se verifican permisos (middleware, guards, policies) y qué rutas/pantallas tiene el miembro.
- Modelos existentes de **Evento**, **Actividad**, **Usuario** y cualquier tabla de asignaciones o invitaciones ya existente.
- Servicio de **envío de correos** (si existe) y cómo reporta fallos.
- Si existe un mecanismo de **tareas programadas** (cron, cola, scheduler).
- Sistema de diseño de los miembros: variables, componentes de tarjeta, tabla, badge, pestañas, modal, botones y campos.

Si algo ya existe, **extiéndelo** en lugar de duplicarlo. Si un campo que piden los diseños no existe, créalo mediante migración (ver sección 4).

---

## 3. Rol participante

- El participante tiene **todos los permisos del miembro + los permisos de confirmación de participaciones**. Implementa esto por herencia o composición de permisos (según el modelo existente), no copiando la lista de permisos a mano.
- Permisos nuevos (nombres orientativos):
  - `participaciones.ver_propias`, `participaciones.responder_propias` → participante.
  - `participaciones.supervisar`, `participaciones.cancelar`, `participaciones.reenviar`, `participaciones.reasignar` → administrador.
- El participante **no** obtiene ningún permiso administrativo ni acceso a invitaciones de otros usuarios.
- Los permisos se validan **en el backend** en cada endpoint; la interfaz solo los refleja (ocultando la opción de menú cuando no corresponde).

---

## 4. Base de datos (derivado del diseño)

### 4.1 Campos requeridos en Actividad / Evento

La tarjeta del participante y la tabla del administrador muestran estos datos. Verifica que existan; si no, agrégalos con migración (nullable para no romper datos existentes):

| Dato en pantalla | Entidad | Campo sugerido | Notas |
|---|---|---|---|
| "Culto de jóvenes" | Evento | `nombre` | |
| "Alabanza" | Actividad | `nombre` | |
| "Sábado, 17 de octubre" | Actividad | `fecha` | |
| "7:00 p. m. – 7:30 p. m." | Actividad | `hora_inicio`, `hora_fin` | Guardar con zona horaria o en UTC; mostrar en America/Bogota |
| "Templo central" | Actividad (o Evento) | `lugar` | **Nuevo respecto al prompt anterior**; si el lugar vive en el evento, heredarlo |
| "Dirigir los cantos de apertura…" | Actividad | `descripcion` | |
| "Responsable: Alejandra Vega Campos · Alabanza" | Actividad | `responsable_id` (FK usuario) + área/ministerio del responsable | El texto tras "·" es el área o ministerio; usa el campo existente o documenta si falta |

### 4.2 Nueva tabla `invitaciones_participacion`

Modelo de asignación:
- Un **evento** tiene un cronograma con **varias actividades**.
- Cada **actividad** tiene **un solo participante** asignado a la vez.
- Actividades distintas del mismo evento pueden tener participantes diferentes, y un mismo participante puede estar en varias actividades.

Una actividad puede acumular **varias invitaciones a lo largo del tiempo** (rechazos, vencimientos, cancelaciones, reasignaciones, revocaciones), pero **solo una puede estar activa** (`pendiente` o `aceptada`). Las demás son historial.

Si el modelo actual guarda el participante directamente en la actividad (por ejemplo `actividad.participante_id`), mantenlo sincronizado con la invitación activa dentro de la misma transacción, o reemplázalo por una consulta a la invitación activa. Documenta cuál elegiste.

En el diseño, "Estudio bíblico" aparece con Regino y con Tomás. Bajo esta regla no pueden ser dos invitaciones activas a la vez: corresponden a actividades distintas del cronograma, o una de las dos es historial. Verifica los datos y no lo reproduzcas como dos asignaciones simultáneas.

| Campo | Tipo | Regla |
|---|---|---|
| `id` | PK | |
| `actividad_id` | FK actividad | obligatorio |
| `participante_id` | FK usuario | obligatorio; el usuario debe tener rol participante |
| `estado_respuesta` | enum: `pendiente`, `aceptada`, `rechazada`, `vencida`, `cancelada`, `reasignada`, `revocada` | default `pendiente`. `reasignada` = la invitación liberada (rechazada/vencida/cancelada) ya tiene reemplazo; `revocada` = una aceptada que el admin retiró para asignar a otra persona |
| `estado_previo` | enum null | estado que tenía antes de pasar a `reasignada` (para mostrar "rechazó" / "no respondió a tiempo" en el historial) |
| `revocada_por`, `fecha_revocacion` | FK usuario / datetime null | auditoría de "Revocar y cambiar" |
| `notificacion_revocacion_estado` | enum null: `enviada`, `error` | resultado del aviso al participante revocado |
| `estado_envio` | enum: `en_cola`, `enviada`, `error` | **independiente** de `estado_respuesta` |
| `fecha_envio` | datetime null | se llena cuando el correo se envía con éxito ("Enviada 4 oct 2026") |
| `intentos_envio` | int | default 0 |
| `ultimo_error_envio` | texto null | solo visible para el administrador / logs; nunca para el participante |
| `fecha_limite_respuesta` | datetime null | "Responde antes del 11 oct" |
| `fecha_respuesta` | datetime null | "Respondió el 2 oct 2026" |
| `motivo_rechazo` | varchar(**255**) null | el modal muestra contador 0/255 |
| `invitada_por` | FK usuario (admin) | auditoría |
| `cancelada_por`, `fecha_cancelacion` | FK usuario / datetime null | auditoría de "Cancelar invitación" |
| `reemplaza_invitacion_id` | FK self null | enlaza la nueva invitación creada al **Reasignar** con la anterior |
| `created_at`, `updated_at` | timestamps | `created_at` = "Invitación recibida el 5 oct" si no hay `fecha_envio` |

Restricciones e índices:
- Unicidad: como máximo **una invitación activa** (`pendiente` o `aceptada`) **por `actividad_id`**, sin importar el participante. Usa un índice único parcial (`UNIQUE (actividad_id) WHERE estado_respuesta IN ('pendiente','aceptada')`) si el motor lo soporta. Si no, valida en el servicio con bloqueo de la fila de la actividad dentro de la transacción.
- Crear una invitación para una actividad que ya tiene una activa → `409`. Para cambiar de persona se usa Cancelar, Reasignar o Revocar, nunca una segunda invitación.
- Opcional, solo como advertencia sin bloquear: avisar al admin si el participante elegido ya tiene otra actividad activa que se cruza en horario.
- Índices en `participante_id + estado_respuesta`, `actividad_id`, `estado_envio`, `fecha_limite_respuesta`.
- Check: `motivo_rechazo` solo puede tener valor si `estado_respuesta = rechazada`.

### 4.3 Valor derivado "Pendiente de asignación" / "Por reasignar"

Una invitación **requiere reasignación** cuando:
- `estado_respuesta ∈ {rechazada, vencida, cancelada}` **y**
- no existe una invitación más reciente con `reemplaza_invitacion_id` apuntando a ella **y**
- la actividad todavía no ha empezado y queda al menos 1 día completo antes de su inicio (si no, ya no hay plazo para pedir confirmación).

Las invitaciones `reasignada` y `revocada` **nunca** cuentan como pendientes de asignación: son historial.

Define explícitamente qué se muestra para una actividad liberada cuyo evento ya pasó (por ejemplo "Lectura bíblica", vencida, 7 oct): no cuenta en "Por reasignar" ni en el banner y no muestra acción, pero conserva su badge de estado.

Calcúlalo en consulta (vista, scope o subconsulta), no como columna editable a mano. Es lo que alimenta el sub-badge "Pendiente de asignación", el filtro "Por reasignar" y el banner.

### 4.4 Vencimiento

- Una invitación `pendiente` con `fecha_limite_respuesta < ahora` pasa a `vencida`.
- Implementa ambas cosas: (a) una tarea programada que actualice los estados (si existe scheduler) y (b) una verificación en el endpoint de responder, para que **nunca** se acepte o rechace una invitación vencida aunque el job no haya corrido.
- Si no hay scheduler, calcula el estado efectivo al consultar y documenta la limitación.

---

## 5. Reglas de transición de estados

| Desde | Acción | Hacia | Quién | Condiciones |
|---|---|---|---|---|
| `pendiente` | Aceptar | `aceptada` | participante dueño | no vencida, no cancelada; guarda `fecha_respuesta` |
| `pendiente` | Rechazar | `rechazada` | participante dueño | motivo opcional ≤ 255; guarda `fecha_respuesta` |
| `pendiente` | Vence plazo | `vencida` | sistema | `fecha_limite_respuesta < ahora` |
| `pendiente` | Cancelar | `cancelada` | admin | la actividad queda sin asignar para ese participante |
| `rechazada` / `vencida` / `cancelada` | Reasignar | original → `reasignada` (guarda `estado_previo`) + nueva invitación `pendiente` | admin | se enlazan por `reemplaza_invitacion_id`; la actividad no debe haber empezado |
| `aceptada` | Revocar y cambiar | original → `revocada` + nueva invitación `pendiente` | admin | guarda `revocada_por` y `fecha_revocacion`; **notifica realmente** al participante revocado (ver 6.2) |
| cualquiera con `estado_envio = error` y respuesta `pendiente` | Reenviar | `estado_envio = enviada` o `error` | admin | incrementa `intentos_envio` |

- Una respuesta **no puede cambiarse** una vez registrada (la pestaña "Respondidas" del diseño no tiene acciones). Si el backend ya permite cambios, respeta esa regla y documéntala.
- Reasignar y revocar son **una sola operación atómica**: cambio de estado de la original + creación de la nueva. Si falla la creación, la original no cambia. El envío de correos va después del commit; si falla, queda registrado en `estado_envio` / `notificacion_revocacion_estado` sin deshacer la operación.
- Las transiciones se ejecutan en **transacción con bloqueo de fila** (o comparación de estado en el `UPDATE … WHERE estado_respuesta = 'pendiente'`) para evitar dobles respuestas simultáneas.
- Un fallo de correo **nunca** altera `estado_respuesta`: en el diseño, la invitación de Tomás aparece "Error de envío" y "Pendiente" a la vez.
- La invitación es visible para el participante en la app aunque el correo haya fallado.

---

## 6. API

Respeta prefijos, formato de respuesta y manejo de errores existentes. Fechas en ISO 8601; el formateo ("17 oct 2026", "7:00 p. m.") lo hace el frontend con locale `es-CO` y zona `America/Bogota`.

### 6.1 Participante (solo sus propias invitaciones)

**`GET /participante/invitaciones?vista=pendientes|respondidas|todas`**
- `pendientes` = `estado_respuesta = pendiente`.
- `respondidas` = todas las que no están pendientes (aceptada, rechazada, vencida, cancelada).
- Orden: pendientes por `fecha_limite_respuesta` ascendente; el resto por fecha de actividad descendente.
- Respuesta:
```json
{
  "conteos": { "pendientes": 2, "respondidas": 4, "todas": 6 },
  "items": [{
    "id": 0,
    "estado_respuesta": "pendiente",
    "fecha_invitacion": "…",
    "fecha_limite_respuesta": "…",
    "fecha_respuesta": null,
    "motivo_rechazo": null,
    "evento": { "id": 0, "nombre": "…" },
    "actividad": { "id": 0, "nombre": "…", "fecha": "…", "hora_inicio": "…", "hora_fin": "…", "lugar": "…", "descripcion": "…" },
    "responsable": { "nombre": "…", "area": "…" }
  }]
}
```
- **No** incluye `estado_envio`, `ultimo_error_envio`, datos de otros participantes ni información administrativa.

**`POST /participante/invitaciones/:id/aceptar`**

**`POST /participante/invitaciones/:id/rechazar`** — body `{ "motivo": "string ≤ 255, opcional" }`

Para ambos:
- `404` si la invitación no existe **o no pertenece al usuario** (no revelar existencia de invitaciones ajenas).
- `409` con `{ "estado_actual": "…" }` si ya fue respondida, vencida o cancelada; el frontend usa ese estado para refrescar la tarjeta.
- `422` si el motivo supera 255 caracteres.
- `200` devuelve la invitación actualizada (mismo DTO que el listado) para que la UI actualice solo tras confirmación del servidor.
- Rechazar deja la invitación lista para aparecer en "Por reasignar" del administrador.

### 6.2 Administrador

**`GET /admin/participaciones?filtro=todas|pendientes|aceptadas|por_reasignar|error_envio&q=&pagina=`**
- Filtros (no son mutuamente excluyentes; "Error de envío" se cruza con "Pendientes"):
  - `pendientes`: `estado_respuesta = pendiente`.
  - `aceptadas`: `estado_respuesta = aceptada`.
  - `por_reasignar`: regla de la sección 4.3.
  - `error_envio`: `estado_envio = error`.
- `q`: búsqueda en servidor sobre nombre de actividad, nombre de evento y nombre del participante, sin distinguir mayúsculas ni tildes (placeholder: "Actividad, evento o participante").
- Orden por fecha y hora de la actividad ascendente.
- Respuesta:
```json
{
  "conteos": { "todas": 9, "pendientes": 4, "aceptadas": 2, "por_reasignar": 2, "error_envio": 1 },
  "alertas": { "actividades_por_reasignar": 2, "invitaciones_error_envio": 1 },
  "items": [{
    "id": 0,
    "actividad": { "id": 0, "nombre": "…", "fecha": "…", "hora_inicio": "…", "hora_fin": "…" },
    "evento": { "id": 0, "nombre": "…" },
    "participante": { "id": 0, "nombre_completo": "…" },
    "estado_envio": "enviada",
    "fecha_envio": "…",
    "estado_respuesta": "vencida",
    "fecha_respuesta": null,
    "motivo_rechazo": null,
    "requiere_reasignacion": true,
    "acciones_permitidas": ["reasignar"]
  }]
}
```
- `conteos` respetan `q` (el mismo término filtra todas las pestañas).
- `alertas` alimenta el banner: "2 actividades necesitan una nueva asignación y 1 invitación no se pudo enviar." Ocúltalo si ambos son 0.
- `acciones_permitidas` lo calcula el backend según la sección 5; el frontend solo pinta los botones que vengan ahí:
  - `pendiente` → `cancelar` (icono ⊘).
  - `pendiente` + `error_envio` → `reenviar`, `cancelar`.
  - `requiere_reasignacion` → `reasignar`.
  - `aceptada` y la actividad no ha empezado → `revocar_y_cambiar`.
  - `reasignada`, `revocada`, o actividad ya iniciada → ninguna.
- Para `reasignada` y `revocada`, incluye `reemplazo: { participante: { nombre_completo } , fecha_limite_respuesta }` para mostrar "Reasignada a {nombre}" / "Revocada".
- Para la nueva invitación pendiente, `fecha_limite_respuesta` se muestra en la tabla.

**`POST /admin/participaciones/:id/cancelar`** — solo si `pendiente`. Devuelve la fila actualizada. Texto del modal del diseño: "{participante} ya no podrá responder la invitación a «{actividad}». La actividad quedará sin asignar."

**`POST /admin/participaciones/:id/reenviar`** — solo si `estado_envio = error` y respuesta `pendiente`. Si el servicio de correo vuelve a fallar, responde con la fila (`estado_envio: "error"`) y un mensaje claro, no un 500 genérico.

**`GET /admin/participaciones/:id/reasignacion`** — datos para la ventana de Reasignar / Revocar:
```json
{
  "actividad": { "nombre": "…", "fecha": "…", "hora_inicio": "…", "hora_fin": "…" },
  "evento": { "nombre": "…" },
  "asignado_actual": { "nombre_completo": "…" },
  "motivo_liberacion": "rechazo | sin_respuesta | cancelada | aceptada",
  "motivo_rechazo": "texto o null",
  "dias_hasta_evento": 6,
  "dias_para_confirmar_max": 5
}
```
- `dias_hasta_evento` se calcula en días calendario en America/Bogota, desde hoy hasta la fecha de inicio de la actividad.
- `dias_para_confirmar_max = min(30, dias_hasta_evento − 1)`. Si es < 1, la ventana avisa que no queda tiempo para pedir confirmación y deshabilita el envío.

**`POST /admin/participaciones/:id/reasignar`** — body `{ "participante_id": 0, "dias_para_confirmar": 3 }`
- Solo si `requiere_reasignacion`.
- En una transacción: original → `reasignada` (con `estado_previo`) y nueva invitación `pendiente` con `reemplaza_invitacion_id = :id` y `fecha_limite_respuesta = hoy + dias_para_confirmar` (fin del día, America/Bogota). Después envía la invitación por correo. Devuelve ambas filas.

**`POST /admin/participaciones/:id/revocar`** — body `{ "participante_id": 0, "dias_para_confirmar": 3 }`
- Solo si `estado_respuesta = aceptada` y la actividad no ha empezado.
- En una transacción: original → `revocada` y nueva invitación `pendiente` (igual que reasignar).
- **Notificación real al revocado**: envía un correo (y notificación en la app, si existe) indicando que ya no está asignado a la actividad. Registra el resultado en `notificacion_revocacion_estado`. El aviso de la ventana dice "se le notificará", así que no puede ser solo texto. Si el proyecto no tiene servicio de correo, cambia el texto del aviso para que no prometa una notificación y documéntalo como pendiente.
- El participante revocado ve la invitación en "Respondidas" con estado "Revocada" y deja de ver la actividad como confirmada.

Validación de `dias_para_confirmar` (reasignar y revocar), **en el backend** además del frontend:
- Entero (rechazar decimales, texto y vacío) → `422`.
- `1 ≤ dias_para_confirmar ≤ dias_para_confirmar_max`. Si se supera el límite por cercanía del evento → `422` con `{ "dias_hasta_evento": 10, "dias_para_confirmar_max": 9 }`.
- `participante_id`: usuario activo y distinto del asignado actual. Puede tener invitaciones en otras actividades del mismo evento. Si el selector ofrece "usuarios activos" que todavía no tienen el rol participante, decide y documenta: o se filtran solo participantes, o al invitarlos se les asigna el rol (sin dar permisos de admin).
- `409` si la invitación cambió de estado mientras la ventana estaba abierta (por ejemplo, la persona respondió).

**`GET /admin/participantes/elegibles?actividad_id=&q=`** — lista para el selector "Nuevo participante". Excluye al asignado actual y marca, sin excluirlos, a quienes tienen otra actividad del cronograma que se cruza en horario.

**Botón "Ver" del banner** → aplica el filtro `por_reasignar` (o `error_envio` si solo hay errores de envío).

---

## 7. Frontend — Participante: "Confirmar participaciones"

Ruta nueva dentro del layout de miembros; opción de menú visible solo con `participaciones.ver_propias`.

- **Encabezado**: "Confirmar participaciones" + "Actividades de eventos a las que te invitaron. Tienes N invitaciones pendientes de respuesta." (N desde `conteos.pendientes`; variar texto si N = 0 o 1).
- **Pestañas**: "Pendientes · N", "Respondidas · N", "Todas · N" (pestaña inicial: Pendientes).
- **Tarjeta**:
  - Bloque de fecha (mes abreviado en mayúsculas + día).
  - Nombre del evento (pequeño, color de acento), nombre de la actividad (título).
  - Badge de estado arriba a la derecha (ícono + texto, no solo color): Pendiente de respuesta, Aceptada, Rechazada, Vencida, Cancelada.
  - Fila con íconos: día completo, rango horario, lugar.
  - Descripción.
  - "Responsable: **Nombre · Área**" y "Invitación recibida el {fecha}".
  - Pie (solo pendientes): "Responde antes del {fecha}" — **resaltado en ámbar y negrita cuando faltan 2 días o menos**; botones "No puedo participar" (secundario) y "✓ Aceptar participación" (primario).
  - Respondidas: sin botones; mostrar "Respondiste el {fecha}" y, si fue rechazo, el motivo propio.
- **Modal "Rechazar participación"**: ícono, título, nombre de actividad, "evento · fecha · horario", texto "Tu respuesta quedará registrada y el administrador podrá asignar la actividad a otra persona.", textarea "Motivo (opcional)" con contador X/255 y `maxlength=255`, placeholder "Ej. Estaré de viaje ese día", botones "Volver" y "No podré participar" (destructivo).
- **Aceptar**: confirmación ligera (o directa, según el patrón existente), botón con estado de carga, actualización de la tarjeta solo tras `200`.
- **Errores**: en `409`, refrescar la tarjeta con `estado_actual` y explicar ("Esta invitación ya venció", "fue cancelada", "ya la respondiste"). En error de red, mantener el estado anterior y mostrar mensaje con opción de reintentar.
- Estados: cargando (skeleton de tarjetas), vacío por pestaña, error de carga, éxito (toast).

## 8. Frontend — Administrador: "Participaciones"

- Encabezado: "Participaciones" + "Invitaciones enviadas a participantes y sus respuestas, por actividad."
- Banner ámbar con `alertas` y botón "Ver".
- Pestañas con conteos + buscador con debounce (≈300 ms).
- **Columnas**:
  - Actividad: nombre + "Evento · fecha · hora_inicio – hora_fin".
  - Participante: avatar con iniciales + nombre completo.
  - Envío: "✉ Enviada {fecha}" o badge rojo "Error de envío".
  - Respuesta: badge (Pendiente, Aceptada, Rechazada, Vencida, Cancelada); debajo "Respondió el {fecha}" o "Pendiente de asignación" cuando `requiere_reasignacion`. Motivo de rechazo visible en tooltip o detalle.
  - Acciones: según `acciones_permitidas` (Reasignar primario, Reenviar secundario, "Revocar y cambiar" con borde rojo en aceptadas, ⊘ cancelar con `aria-label="Cancelar invitación a {participante}"`).
  - Filas `reasignada` / `revocada`: badge neutro "Reasignada a {nombre}" o "Revocada", sin acciones.
- **Ventana "Reasignar" / "Revocar confirmación y cambiar participante"** (un solo componente, dos modos):
  - Encabezado: título, nombre de la actividad, "Evento · fecha · horario", botón × de cierre.
  - Tarjeta "Asignado actualmente": nombre y motivo de liberación ("Rechazó: {motivo}", "No respondió a tiempo", "Invitación cancelada" o "Confirmó su participación").
  - Solo en modo revocar: aviso rojo "Su confirmación quedará revocada y se le notificará que ya no está asignado a esta actividad."
  - "Nuevo participante": selector desde `/admin/participantes/elegibles`.
  - "Días para confirmar": campo numérico manual (`inputmode="numeric"`, solo enteros) con sufijo "días". Ayuda dinámica: "Entre 1 y {max} días. El evento es el {fecha} (en {n} días)." Al escribir un valor válido, mostrar la fecha límite resultante y cuántos días antes del evento cae. Si se supera el máximo: "El evento empieza en {n} días. El plazo máximo es de {max} días." y botón deshabilitado.
  - Si `dias_para_confirmar_max < 1`: mensaje de que no queda tiempo para pedir confirmación, sin formulario de envío.
  - Botones: "Cancelar" y "Reasignar y enviar invitación" / "Revocar y enviar invitación" (destructivo en modo revocar), con estado de carga; la tabla se actualiza solo tras `200`.
  - Errores `422` se muestran junto al campo; `409` cierra la ventana, refresca la fila y explica qué cambió.
- Modal "Cancelar invitación" con texto del diseño; botones "Cancelar" (cerrar) y "Cancelar invitación" (destructivo). Considera renombrar el botón de cierre a "Volver" para evitar la ambigüedad de dos botones "Cancelar".
- En móvil, la tabla pasa a lista de tarjetas con la misma información.

## 9. Sistema visual

Reutiliza los tokens y componentes de los miembros (fondo crema, verde oscuro primario, rojo para acciones destructivas, ámbar para pendientes/alertas, badges redondeados con ícono, tarjetas con borde suave y radio grande, pestañas tipo segmented control). No crees un sistema visual nuevo ni introduzcas estilos globales que alteren otras pantallas. Accesibilidad WCAG 2.2 AA: contraste, foco visible (como el anillo verde de las pestañas), navegación por teclado, modales con foco atrapado y cierre con Esc, estados que no dependan solo del color.

## 10. Datos

- Usa solo datos reales del backend. Los nombres de las capturas (Regino Puentes Meza, Elena Cruz Mora, etc.) son ilustrativos: **no** los insertes en datos de la app; solo pueden usarse en seeds de desarrollo o fixtures de pruebas, claramente marcados.
- No simules endpoints ni respuestas.

## 11. Pruebas mínimas

Backend:
- Participante solo ve sus invitaciones; acceder a una ajena devuelve 404.
- Miembro sin rol participante recibe 403 en los endpoints de participante; participante recibe 403 en endpoints `/admin`.
- Aceptar/rechazar una invitación ya respondida, vencida o cancelada → 409.
- Dos respuestas concurrentes a la misma invitación → solo una se registra.
- Motivo > 255 → 422.
- Rechazo, vencimiento y cancelación aparecen en `por_reasignar`; tras reasignar, la original deja de aparecer.
- Fallo de correo deja `estado_envio = error` sin cambiar `estado_respuesta`.
- Conteos y alertas coinciden con los items filtrados.
- El participante conserva todos los permisos del miembro.
- Reasignar deja la original en `reasignada`, crea la nueva `pendiente` con la fecha límite correcta y la actividad sale de "Por reasignar".
- Revocar una aceptada la deja en `revocada`, crea la nueva invitación y dispara la notificación al revocado (verificar con el servicio de correo simulado en tests, no en producción).
- `dias_para_confirmar`: 0, 31, 2.5, texto y valores mayores que `dias_hasta_evento − 1` → 422; el límite exacto se acepta.
- Actividad que empieza mañana o ya pasó: no aparece en "Por reasignar", no ofrece Revocar y los endpoints rechazan la operación.
- Si falla la creación de la nueva invitación, la original conserva su estado (rollback).
- Una actividad nunca tiene dos invitaciones activas: crear una segunda → 409. Dos reasignaciones concurrentes de la misma actividad → solo una se registra.
- Un mismo participante puede tener invitaciones activas en varias actividades del mismo evento.

Frontend: renderizado de cada estado de tarjeta y fila, apertura/cierre de modales, contador de motivo, manejo de 409 y errores de red, visibilidad de la opción de menú por rol.

## 12. Entregables

1. Migraciones y cambios de modelos.
2. Endpoints, validaciones y permisos.
3. Páginas, componentes y navegación.
4. Pruebas ejecutadas y resultados.
5. Informe final con: archivos modificados, decisiones tomadas donde el modelo existente difería de este prompt (por ejemplo, actividades con un solo asignado), limitaciones (scheduler, servicio de correo) y tareas pendientes.

No te detengas tras presentar un plan: inspecciona, implementa, prueba e informa.
