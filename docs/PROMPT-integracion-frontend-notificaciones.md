# Prompt — Integración Frontend: Notificaciones (Church Connect)

> Copia este bloque completo y pásalo a tu asistente de código (o úsalo como especificación de la tarea).
> Describe el contrato real del backend `Church-Connect-backend` (FastAPI) para el módulo
> **Notificaciones**, incluyendo el nuevo **envío masivo**, y la estructura que debe implementarse
> en `Church-Connect-Frontend` (React 19 + Vite + TypeScript + TailwindCSS v4 + react-router-dom 7).
>
> **Depende de** la integración de autenticación ya implementada
> (`docs/PROMPT-integracion-frontend-auth-users.md`): reutiliza `lib/httpClient.ts`,
> `auth/AuthContext`, `ProtectedRoute`, el envelope `ResponsePayload<T>` y el token en
> `localStorage` (`cc_token`). Este documento **solo agrega** el módulo de notificaciones.

---

## 1. Objetivo

Implementar en el frontend:

1. Una **bandeja de notificaciones** para cualquier usuario autenticado, mostrando **solo las suyas**.
2. Un **panel de envío** (solo `ADMIN`) para notificar a **un usuario** o a **varios usuarios a la vez**
   (envío masivo), cada uno recibiendo una notificación registrada en BD + un correo (best-effort).

Dos niveles de acceso:

- **Lectura de la propia bandeja** (listar / ver detalle): cualquier usuario autenticado
  (`ADMIN`, `PARTICIPANT`, `MEMBER`). **Nadie puede ver notificaciones de otro usuario**, ni
  siquiera `ADMIN` — no existe un endpoint de "bandeja global".
- **Envío / edición / eliminación**: **solo `ADMIN`**.

## 2. Configuración base de la API

| Concepto | Valor |
|---|---|
| Base URL (dev) | `http://localhost:8000` (configurable vía `VITE_API_URL`) |
| Prefijo global | `/api/v1` |
| Prefijo del módulo | `/notificaciones` |
| Auth | `Authorization: Bearer <access_token>` en **todos** los endpoints (no hay endpoints públicos) |
| Formato | JSON en request y response |

Todas las respuestas usan el envelope `ResponsePayload`:

```json
{
  "statusCode": 200,
  "status": "OK",
  "data": {},
  "success": true,
  "message": "Mensaje descriptivo",
  "errors": null,
  "timestamp": "2026-09-20T12:00:00Z",
  "meta": null
}
```

- Error: `success: false`, `data: null`, `errors: ["detalle", ...]`.
- En errores `HTTPException` (`400/401/403/404`) el backend repite el detalle en `message` **y** en `errors[0]`.
- Validación (`422`): `message: "Error de validación en los datos enviados"`,
  `errors: ["body.campo: mensaje", ...]`.
- Paginación del listado: `meta.totalNotificaciones` trae el conteo total real del usuario
  autenticado, independiente de `limit`/`offset`.
- El envío masivo devuelve un `meta` distinto (`{ total, exitosas, fallidas }`) — ver §4.3.

El `httpClient` ya desempaca `data` y lanza `ApiError` (con `message` + `errors` + `status`) ante `success: false`.

## 3. Modelo de datos

### `Notification` — `NotificationResponse` (lo que devuelve la API)

| Campo | Tipo | Notas |
|---|---|---|
| `id` | `string` (UUID) | |
| `titulo` | `string` | |
| `mensaje` | `string` | |
| `usuario_id` | `string` (UUID) | destinatario |
| `leida` | `boolean` | default `false` al crearse |
| `fecha_envio` | `string` (ISO datetime) | se asigna en el servidor al crear |

> **Limitación conocida:** marcar una notificación como `leida` se hace vía
> `PUT /notificaciones/{id}`, pero ese endpoint es **solo `ADMIN`**. Hoy un usuario normal
> **no puede** marcar sus propias notificaciones como leídas por sí mismo — la API no expone
> ese caso de uso todavía. Si la UI necesita "marcar como leída" para el dueño de la
> notificación, hay que pedir al backend un endpoint dedicado (p. ej.
> `PATCH /notificaciones/{id}/leida`, self-service). Mientras tanto, omitir ese botón para
> roles no `ADMIN`, o dejarlo deshabilitado con un tooltip explicativo.

## 4. Endpoints a consumir

Todos cuelgan de `/api/v1/notificaciones`. Todos requieren `Authorization: Bearer <token>`.
Sin token → `401`. Rol insuficiente → `403 "No tiene permisos para realizar esta acción"`.

### 4.1 Listar mis notificaciones — `GET /api/v1/notificaciones`

- **Auth:** cualquier usuario autenticado. El backend **siempre filtra por el usuario del token**
  (no hay parámetro para pedir las de otro usuario ni una vista "todas").
- **Query:** `limit` (1–100, default `10`), `offset` (>= 0, default `0`).
- **200:** `data` = `NotificationResponse[]`, `meta.totalNotificaciones` = total.
  `message: "Notificaciones obtenidas exitosamente"`.
- **401** sin token.

### 4.2 Obtener notificación por ID — `GET /api/v1/notificaciones/{notificacion_id}`

- **Auth:** cualquier usuario autenticado, pero **solo el dueño** puede verla.
- **200:** `data` = `NotificationResponse`. `message: "Notificación obtenida exitosamente"`.
- **403:** `"No tiene permisos para ver esta notificación"` (existe pero es de otro usuario).
- **404:** `"Notificación no encontrada"`.
- **422:** `notificacion_id` no es un UUID válido.

### 4.3 Crear notificación individual — `POST /api/v1/notificaciones`

- **Auth:** **solo `ADMIN`**.
- **Body:**
  ```json
  { "titulo": "Revisa", "mensaje": "Va a funcionar todo bien con la ayuda de Dios", "usuario_id": "d96d095e-0a9b-4f98-b89d-0e63afc6e08e" }
  ```
- **201:** `data` = `NotificationResponse` creada. `message: "Notificación creada exitosamente"`.
  El correo se envía en segundo plano (best-effort): si falla o no hay SMTP configurado, la
  notificación **igual se crea**. El frontend no tiene forma de saber si el correo llegó para
  este endpoint individual (a diferencia del masivo, ver abajo).
- **403** no admin · **404** `"Usuario no encontrado"` · **422** campos inválidos/faltantes.

### 4.4 Envío masivo — `POST /api/v1/notificaciones/masivo`

Crea la **misma** notificación (título + mensaje) para una lista de usuarios. Cada usuario se
procesa de forma independiente: si uno falla, no afecta a los demás.

- **Auth:** **solo `ADMIN`**.
- **Body:**
  ```json
  {
    "titulo": "Reunión general",
    "mensaje": "Los esperamos el sábado a las 5pm",
    "usuarios_ids": [
      "d96d095e-0a9b-4f98-b89d-0e63afc6e08e",
      "1c2b3a4d-5e6f-4a1b-8c9d-0e1f2a3b4c5d"
    ]
  }
  ```

Respuestas posibles (según cuántos usuarios se procesaron con éxito):

| Caso | HTTP | `success` | `data` | `errors` | `meta` |
|---|---|---|---|---|---|
| Todos exitosos | `201` | `true` | `NotificationResponse[]` (todas las creadas) | `null` | `{ total, exitosas, fallidas: 0 }` |
| Éxito parcial | `207` | `true` | `NotificationResponse[]` (solo las creadas) | `["<usuario_id>: <motivo>", ...]` | `{ total, exitosas, fallidas }` |
| Cero éxitos | `500` | `false` | `null` | `["<usuario_id>: <motivo>", ...]` | `{ total, exitosas: 0, fallidas }` |
| `usuarios_ids` vacío/ausente | `400` | `false` | `null` | `["Debe indicar al menos un usuario en usuarios_ids"]` | `null` |

Ejemplo `207`:

```json
{
  "statusCode": 207,
  "status": "MultiStatus",
  "data": [ { "id": "...", "titulo": "Reunión general", "...": "..." } ],
  "success": true,
  "message": "Se enviaron 3 notificaciones exitosamente y 2 fallaron",
  "errors": [
    "1c2b3a4d-...: Usuario no encontrado",
    "9a8b7c6d-...: <detalle del error de base de datos>"
  ],
  "meta": { "total": 5, "exitosas": 3, "fallidas": 2 },
  "timestamp": "2026-09-20T16:49:55.327962Z"
}
```

> Igual que en la creación individual, el envío de correo es **best-effort**: `exitosas` cuenta
> notificaciones **registradas en BD** (usuario válido + insert exitoso), no confirma que el
> correo haya sido entregado. Si el proveedor SMTP falla, la notificación queda creada igual.

**Mapeo a Toasts (criterios de aceptación del producto):**

| Respuesta | Toast |
|---|---|
| `201` | `"Se enviaron {exitosas} notificaciones exitosamente."` |
| `207` | `"Se enviaron {exitosas} notificaciones exitosamente y {fallidas} fallaron."` |
| `500` (o error de red genérico) | `"Error al procesar la solicitud. Ninguna notificación pudo ser enviada."` |
| `400` | Mensaje de validación en el propio formulario: "Selecciona al menos un destinatario." |

> No asumas que el texto de `message` del backend siempre coincide 1:1 con el toast deseado
> (por ejemplo, en `500` el backend responde `"No se pudo enviar ninguna notificación"`); usa la
> tabla de arriba como copy definitivo del frontend, basado en el **status code**, no en `message`.

### 4.5 Actualizar notificación — `PUT /api/v1/notificaciones/{notificacion_id}` (parcial)

- **Auth:** **solo `ADMIN`** (ver limitación en §3 sobre "marcar como leída").
- **Body (todos opcionales, se actualiza solo lo enviado):**
  ```json
  { "titulo": "Nuevo título", "mensaje": "Nuevo mensaje", "leida": true }
  ```
  `usuario_id` **no es modificable** (no se puede reasignar el destinatario).
- **200:** `data` = `NotificationResponse` actualizada. `message: "Notificación actualizada exitosamente"`.
- **403** no admin · **404** `"Notificación no encontrada"` · **422** campos inválidos.

### 4.6 Eliminar notificación — `DELETE /api/v1/notificaciones/{notificacion_id}`

- **Auth:** **solo `ADMIN`**.
- **200:** `data: null`, `message: "Notificación eliminada exitosamente"`.
- **403** no admin · **404** `"Notificación no encontrada"`.

### Matriz de permisos

| Acción | ADMIN | PARTICIPANT / MEMBER | Sin token |
|---|---|---|---|
| Ver mi bandeja / detalle propio | ✅ | ✅ | ❌ 401 |
| Ver detalle de otro usuario | ❌ 403 | ❌ 403 | ❌ 401 |
| Crear notificación individual | ✅ | ❌ 403 | ❌ 401 |
| Envío masivo | ✅ | ❌ 403 | ❌ 401 |
| Editar / marcar leída / eliminar | ✅ | ❌ 403 | ❌ 401 |

## 5. Estructura a implementar en el frontend

Se **agrega** sobre la estructura ya existente del módulo de auth/usuarios:

```
src/
├── types/
│   └── notification.ts        # Notification, CreateNotificationDTO, BulkNotificationDTO,
│                               # BulkNotificationResult, UpdateNotificationDTO
├── services/
│   └── notificationService.ts # list, getById, create, createBulk, update, remove
├── hooks/
│   ├── useNotifications.ts    # bandeja propia + paginación (meta.totalNotificaciones) + refetch
│   └── useNotification.ts     # detalle propio por id
├── pages/
│   └── notifications/
│       ├── NotificationsInboxPage.tsx   # todos los roles: mis notificaciones
│       ├── NotificationDetailPage.tsx   # detalle (leída deshabilitado si no ADMIN, ver §3)
│       ├── NotificationSendPage.tsx     # ADMIN: tabs "Individual" | "Masivo"
│       └── components/
│           ├── NotificationsList.tsx
│           ├── NotificationForm.tsx         # individual: selector de 1 usuario (userService.list)
│           ├── BulkNotificationForm.tsx     # masivo: multi-select de usuarios + título + mensaje
│           └── BulkResultSummary.tsx        # renderiza data/errors/meta de la respuesta 207
└── router.tsx                 # + rutas de notificaciones (ver §7)
```

### Contratos TypeScript

```ts
// types/notification.ts
export interface Notification {
  id: string;
  titulo: string;
  mensaje: string;
  usuario_id: string;
  leida: boolean;
  fecha_envio: string; // ISO datetime
}

export interface CreateNotificationDTO {
  titulo: string;
  mensaje: string;
  usuario_id: string;
}

export interface BulkNotificationDTO {
  titulo: string;
  mensaje: string;
  usuarios_ids: string[];
}

export interface BulkNotificationMeta {
  total: number;
  exitosas: number;
  fallidas: number;
}

// Resultado ya normalizado para la UI (ver httpClient en §6)
export interface BulkNotificationResult {
  status: 201 | 207 | 500;
  data: Notification[];
  errors: string[] | null;
  meta: BulkNotificationMeta;
}

export interface UpdateNotificationDTO {
  titulo?: string;
  mensaje?: string;
  leida?: boolean;
}
```

### `services/notificationService.ts` (firma esperada)

```ts
const BASE = "/notificaciones";

export const notificationService = {
  list: (params?: { limit?: number; offset?: number }) =>
    http.getPaginated<Notification>(BASE, params, "totalNotificaciones"),

  getById: (id: string) =>
    http.get<Notification>(`${BASE}/${id}`),

  create: (dto: CreateNotificationDTO) =>
    http.post<Notification>(BASE, dto),

  // El envío masivo puede responder 201/207/500 con cuerpo válido en los tres
  // casos: no tratarlo como error salvo 400/401/403/422. Ver §6 sobre httpClient.
  createBulk: (dto: BulkNotificationDTO) =>
    http.postRaw<Notification[]>(`${BASE}/masivo`, dto),

  update: (id: string, dto: UpdateNotificationDTO) =>
    http.put<Notification>(`${BASE}/${id}`, dto),

  remove: (id: string) =>
    http.delete<null>(`${BASE}/${id}`),
};
```

## 6. Ajuste necesario en `httpClient`

El interceptor actual probablemente trata **cualquier status fuera de 2xx** como error y lanza
`ApiError`. El envío masivo rompe ese supuesto: `207` es 2xx (no hay ajuste ahí), pero **`500`
con este endpoint sí trae un `ResponsePayload` válido y usable** (`errors` con el detalle por
usuario), no un error genérico de servidor.

Se recomienda agregar `http.postRaw<T>(url, body)` que:

1. Hace el `POST` normalmente (con el `Authorization` header ya inyectado).
2. **No** lanza `ApiError` si el status es `201`, `207` o `500` **y** el cuerpo es un
   `ResponsePayload` parseable — en esos tres casos devuelve `{ status, data, errors, meta }` tal
   cual para que la página decida el toast (tabla de §4.4).
3. Sigue lanzando `ApiError` para `400/401/403/422` y para cualquier `500` que no traiga el
   envelope esperado (error real de red/servidor, no del dominio de negocio).

No modificar el comportamiento de `http.get/post/put/delete` existentes — son para los demás
endpoints donde 2xx = éxito, no-2xx = error, tal como ya funciona hoy.

## 7. Requisitos funcionales

1. **Bandeja (`/notificaciones`):** visible para cualquier usuario autenticado, muestra
   **solo sus propias** notificaciones (el backend ya filtra; no hay filtro de usuario en la UI).
   Lista con `titulo`, `fecha_envio` (formateada), indicador visual de `leida`. Paginación
   server-side con `limit`/`offset` y total desde `meta.totalNotificaciones`.
2. **Detalle (`/notificaciones/:id`):** `titulo`, `mensaje`, `fecha_envio`. Botón "Marcar como
   leída" **solo visible si `role === "ADMIN"`** (ver limitación §3); para el resto de roles,
   ocultarlo o deshabilitarlo con tooltip. `403`/`404` → pantalla de error con enlace a la bandeja.
3. **Envío individual (`NotificationSendPage`, tab "Individual"):** `ProtectedRoute
   requiredRole="ADMIN"`. Formulario con selector de 1 usuario (`userService.list()`), `titulo` y
   `mensaje` (`textarea`). Éxito (`201`) → toast + limpiar formulario.
4. **Envío masivo (`NotificationSendPage`, tab "Masivo"):** `ProtectedRoute
   requiredRole="ADMIN"`. Multi-select de usuarios (checkboxes o combobox multi), `titulo`,
   `mensaje`. Botón deshabilitado si no hay ningún usuario seleccionado (evita el `400` antes de
   enviar). Al responder:
   - `201` → toast éxito (tabla §4.4), limpiar formulario.
   - `207` → toast de advertencia (tabla §4.4) **y** mostrar `BulkResultSummary` con el detalle de
     `errors` (qué usuario falló y por qué), sin limpiar el formulario para permitir reintentar
     solo con los fallidos.
   - `500` → toast de error (tabla §4.4), mantener el formulario intacto para reintentar.
   - `400` (lista vacía) → no debería ocurrir si el botón se deshabilita correctamente, pero
     manejarlo igual como validación de formulario, no como error de servidor.
5. **Manejo de errores:** reutilizar el componente global que renderiza `message` + `errors`
   del `ApiError` para `401/403/404/422`. `401` en cualquier request → `logout()` + redirect a
   `/login` (ya implementado en el interceptor del `httpClient`).
6. **Navegación:** agregar "Notificaciones" al navbar/`AppShell` para todos los roles
   autenticados; el enlace a "Enviar notificación" solo aparece para `ADMIN`.

## 8. Rutas (router.tsx)

```tsx
// dentro del árbol privado (ProtectedRoute base = requiere sesión)
{ path: "notificaciones",         element: <NotificationsInboxPage /> },
{ path: "notificaciones/:id",     element: <NotificationDetailPage /> },
{ path: "notificaciones/enviar",  element: <ProtectedRoute requiredRole="ADMIN"><NotificationSendPage /></ProtectedRoute> },
```

> Definir la ruta `notificaciones/enviar` **antes** de `notificaciones/:id` para que
> `"enviar"` no se interprete como un id.

## 9. Requisitos no funcionales

- Todo llamado a la API pasa por `services/notificationService.ts` → `httpClient` (sin `fetch` suelto).
- Estados de carga y error explícitos en cada pantalla, incluyendo el estado intermedio "enviando..."
  del envío masivo (puede tardar si hay muchos destinatarios, ya que el backend procesa uno por uno).
- Tipado estricto (`strict: true`), sin `any` en servicios ni hooks.
- Los `id` de la URL se tratan como `string`; no parsear a número.
- Reutilizar componentes de formulario/feedback existentes (inputs, toast, spinner, modal).
- Accesibilidad: `label` en cada campo, `aria-invalid`, foco en el primer error, anunciar el
  resultado del envío masivo (`aria-live="polite"`) ya que llega de forma asíncrona tras el submit.
- Respetar el design system (clases semánticas: `bg-card`, `text-foreground`, `border-border`,
  `text-destructive`, `bg-primary`, `ring-ring`).

## 10. Criterios de aceptación (verificable)

- [ ] Cualquier usuario autenticado ve solo sus propias notificaciones en `/notificaciones`,
      paginadas con `meta.totalNotificaciones`.
- [ ] Acceder a la notificación de otro usuario por URL directa muestra el error `403` sin romper la UI.
- [ ] `PARTICIPANT`/`MEMBER` no ven el enlace "Enviar notificación"; el acceso directo por URL a
      `/notificaciones/enviar` los bloquea (redirect/403).
- [ ] `ADMIN` envía una notificación individual y recibe el toast de éxito.
- [ ] `ADMIN` envía un lote donde todos los `usuarios_ids` son válidos → toast
      `"Se enviaron {exitosas} notificaciones exitosamente."`
- [ ] `ADMIN` envía un lote con al menos un `usuario_id` inválido y al menos uno válido → toast
      `"Se enviaron {exitosas} notificaciones exitosamente y {fallidas} fallaron."` y se ve el
      detalle de los fallos en `BulkResultSummary`.
- [ ] `ADMIN` envía un lote donde **todos** los `usuarios_ids` son inválidos → toast de error
      total, sin notificaciones creadas.
- [ ] El botón de envío masivo está deshabilitado si no hay usuarios seleccionados (no llega a
      pegarle un `400` a la API en el flujo normal).
- [ ] Errores `401/403/404/422` se muestran con `message`/`errors` del envelope; `401` cierra
      sesión automáticamente.
- [ ] Ningún componente llama a `fetch` directo; todo pasa por `notificationService`.
