# Prompt — Integración Frontend: CRUD de Ministerios (Church Connect)

> Copia este bloque completo y pásalo a tu asistente de código (o úsalo como especificación de la tarea).
> Describe el contrato real del backend `Church-Connect-backend` (FastAPI) para el módulo **Ministries**
> y la estructura que debe implementarse en `Church-Connect-Frontend`
> (React 19 + Vite + TypeScript + TailwindCSS v4 + react-router-dom 7).
>
> **Depende de** la integración de autenticación ya implementada
> (`docs/PROMPT-integracion-frontend-auth-users.md`): reutiliza `lib/httpClient.ts`,
> `auth/AuthContext`, `ProtectedRoute`, el envelope `ResponsePayload<T>` y el token en
> `localStorage` (`cc_token`). Este documento **solo agrega** el módulo de ministerios.

---

## 1. Objetivo

Implementar en el frontend la **gestión de ministerios** y la **asignación de usuarios a ministerios**
consumiendo la API REST del backend, respetando el control de acceso por roles y el envelope estándar.

Dos niveles de acceso:

- **Lectura** (listar / ver detalle / ver miembros): cualquier usuario autenticado (`ADMIN`, `PARTICIPANT`, `MEMBER`).
- **Escritura** (crear / editar / eliminar ministerios y administrar miembros): **solo `ADMIN`**.

## 2. Configuración base de la API

| Concepto | Valor |
|---|---|
| Base URL (dev) | `http://localhost:8000` (configurable vía `VITE_API_URL`) |
| Prefijo global | `/api/v1` |
| Prefijo del módulo | `/ministries` |
| Auth | `Authorization: Bearer <access_token>` en **todos** los endpoints (no hay endpoints públicos) |
| Formato | JSON en request y response |

Todas las respuestas usan el envelope `ResponsePayload` (ver §4 del documento de auth). Recordatorio:

```json
{
  "statusCode": 200,
  "status": "OK",
  "data": {},
  "success": true,
  "message": "Mensaje descriptivo",
  "errors": null,
  "timestamp": "2026-09-01T12:00:00Z",
  "meta": null
}
```

- Error: `success: false`, `data: null`, `errors: ["detalle", ...]`.
- En errores `HTTPException` (`401/403/404/409`) el backend repite el detalle en `message` **y** en `errors[0]`.
- Validación (`422`): `message: "Error de validación en los datos enviados"`,
  `errors: ["body.nombre: mensaje", ...]`.
- Paginación: `meta.totalMinistries` (listado de ministerios) y `meta.totalMembers`
  (listado de miembros) traen el conteo total real, independiente de `limit`/`offset`.

El `httpClient` ya desempaca `data` y lanza `ApiError` (con `message` + `errors` + `status`) ante `success: false`.

## 3. Modelo de datos

### `Ministry` — `MinistryResponse` (lo que devuelve la API)

| Campo | Tipo | Notas |
|---|---|---|
| `id` | `string` (UUID) | |
| `nombre` | `string` | 1–255 caracteres, requerido |
| `descripcion` | `string \| null` | texto libre, opcional |

> El backend **no** devuelve `fecha_creacion` ni contadores de miembros en el objeto ministerio.
> Si la UI necesita el número de miembros, se obtiene de `meta.totalMembers` del endpoint `GET /ministries/{id}/users`.

### `MinistryMember` — `MinistryMemberResponse` (usuario dentro de un ministerio)

| Campo | Tipo | Notas |
|---|---|---|
| `id` | `string` (UUID) | id del usuario |
| `nombre` | `string` | |
| `apellido` | `string \| null` | |
| `correo` | `string` (email) | |

> Es una vista reducida del usuario (no incluye `rol`, `telefono`, `activo`).
> Para más datos de un miembro, consumir `GET /api/v1/users/{id}` (solo `ADMIN` puede ver perfiles ajenos).

### Relación usuario–ministerio

- Tabla puente `usuarios_ministry` (`usuario_id`, `ministerio_id`).
- Un usuario puede pertenecer a un ministerio **una sola vez** (asignación duplicada → `409`).
- Al **eliminar** un ministerio, las membresías **no se borran**: quedan con `ministerio_id = NULL`
  (regla `ON DELETE SET NULL`). No hay endpoint que liste "usuarios sin ministerio"; tenerlo en cuenta en la UI.

## 4. Endpoints a consumir

Todos cuelgan de `/api/v1/ministries`. Todos requieren `Authorization: Bearer <token>`.
Sin token → `401`. Rol insuficiente → `403 "No tiene permisos para realizar esta acción"`.

### 4.1 Listar ministerios — `GET /api/v1/ministries`

- **Auth:** cualquier usuario autenticado.
- **Query:** `limit` (1–100, default `10`), `offset` (>= 0, default `0`).
- **200:** `data` = `MinistryResponse[]`, `meta.totalMinistries` = total.
  `message: "Ministerios obtenidos exitosamente"`.
- **401** sin token.

### 4.2 Obtener ministerio por ID — `GET /api/v1/ministries/{ministry_id}`

- **Auth:** cualquier usuario autenticado.
- **200:** `data` = `MinistryResponse`. `message: "Ministerio obtenido exitosamente"`.
- **404:** `message: "Ministerio no encontrado"`.
- **422:** `ministry_id` no es un UUID válido.

### 4.3 Crear ministerio — `POST /api/v1/ministries`

- **Auth:** **solo `ADMIN`**.
- **Body:**
  ```json
  { "nombre": "Alabanza", "descripcion": "Equipo de música y adoración" }
  ```
  `nombre` obligatorio (1–255). `descripcion` opcional (puede omitirse o enviarse `null`).
- **201:** `data` = `MinistryResponse` creado. `message: "Ministerio creado exitosamente"`.
- **403** no admin · **422** `nombre` vacío o > 255.

### 4.4 Actualizar ministerio — `PUT /api/v1/ministries/{ministry_id}` (parcial)

- **Auth:** **solo `ADMIN`**.
- **Body (todos opcionales, se actualiza solo lo enviado):**
  ```json
  { "nombre": "Nuevo nombre", "descripcion": "Nueva descripción" }
  ```
  Enviar `descripcion: null` la limpia. `nombre`, si se envía, debe cumplir 1–255.
- **200:** `data` = `MinistryResponse` actualizado. `message: "Ministerio actualizado exitosamente"`.
- **403** no admin · **404** `"Ministerio no encontrado"` · **422** `nombre` inválido.

### 4.5 Eliminar ministerio — `DELETE /api/v1/ministries/{ministry_id}`

- **Auth:** **solo `ADMIN`**.
- **200:** `data: null`, `message: "Ministerio eliminado exitosamente"`.
- **403** no admin · **404** `"Ministerio no encontrado"`.
- **Efecto colateral:** los usuarios que pertenecían al ministerio quedan sin ministerio
  (`ministerio_id → NULL`), no se eliminan. Advertirlo en el modal de confirmación.

### 4.6 Listar usuarios de un ministerio — `GET /api/v1/ministries/{ministry_id}/users`

- **Auth:** cualquier usuario autenticado.
- **Query:** `limit` (1–100, default `10`), `offset` (>= 0, default `0`).
- **200:** `data` = `MinistryMemberResponse[]`, `meta.totalMembers` = total.
  `message: "Usuarios del ministerio obtenidos exitosamente"`.
- **404:** `"Ministerio no encontrado"`.

### 4.7 Asignar usuario a un ministerio — `POST /api/v1/ministries/{ministry_id}/users/{user_id}`

- **Auth:** **solo `ADMIN`**.
- **Body:** ninguno (los dos IDs van en la ruta).
- **201:** `data: null`, `message: "Usuario asignado al ministerio exitosamente"`.
- **403** no admin.
- **404:** ministerio o usuario inexistente → `message: "Ministerio no encontrado"` o `"Usuario no encontrado"`.
- **409:** `message: "El usuario ya pertenece a este ministerio"`.

### 4.8 Quitar usuario de un ministerio — `DELETE /api/v1/ministries/{ministry_id}/users/{user_id}`

- **Auth:** **solo `ADMIN`**.
- **200:** `data: null`, `message: "Usuario removido del ministerio exitosamente"`.
- **403** no admin.
- **404:** `"Ministerio no encontrado"` o `"El usuario no pertenece a este ministerio"`.

### Matriz de permisos

| Acción | ADMIN | PARTICIPANT / MEMBER | Sin token |
|---|---|---|---|
| Listar ministerios | ✅ | ✅ | ❌ 401 |
| Ver ministerio por ID | ✅ | ✅ | ❌ 401 |
| Ver miembros de un ministerio | ✅ | ✅ | ❌ 401 |
| Crear ministerio | ✅ | ❌ 403 | ❌ 401 |
| Editar ministerio | ✅ | ❌ 403 | ❌ 401 |
| Eliminar ministerio | ✅ | ❌ 403 | ❌ 401 |
| Asignar / quitar miembro | ✅ | ❌ 403 | ❌ 401 |

## 5. Estructura a implementar en el frontend

Se **agrega** sobre la estructura ya existente del módulo de auth/usuarios:

```
src/
├── types/
│   └── ministry.ts            # Ministry, MinistryMember, CreateMinistryDTO, UpdateMinistryDTO
├── services/
│   └── ministryService.ts     # list, getById, create, update, remove,
│                              # listMembers, addMember, removeMember
├── hooks/
│   ├── useMinistries.ts       # listado + paginación (meta.totalMinistries) + refetch
│   ├── useMinistry.ts         # detalle por id
│   └── useMinistryMembers.ts  # miembros de un ministerio + paginación (meta.totalMembers) + refetch
├── pages/
│   └── ministries/
│       ├── MinistriesListPage.tsx    # lectura para todos; botón "Nuevo" solo ADMIN
│       ├── MinistryDetailPage.tsx    # datos del ministerio + lista de miembros
│       ├── MinistryCreatePage.tsx    # solo ADMIN
│       ├── MinistryEditPage.tsx      # solo ADMIN
│       └── components/
│           ├── MinistryForm.tsx           # nombre + descripción (create/edit)
│           ├── MinistryMembersList.tsx     # tabla de miembros + paginación
│           ├── AddMemberDialog.tsx         # selector de usuario (usa userService.list) — ADMIN
│           └── DeleteMinistryDialog.tsx    # confirmación + aviso de "quedan sin ministerio"
└── router.tsx                 # + rutas de ministerios (ver §7)
```

### Contratos TypeScript

```ts
// types/ministry.ts
export interface Ministry {
  id: string;
  nombre: string;
  descripcion: string | null;
}

export interface MinistryMember {
  id: string;          // id del usuario
  nombre: string;
  apellido: string | null;
  correo: string;
}

export interface CreateMinistryDTO {
  nombre: string;
  descripcion?: string | null;
}

export interface UpdateMinistryDTO {
  nombre?: string;
  descripcion?: string | null;
}

// Respuestas paginadas (el httpClient debe exponer también `meta`)
export interface Paginated<T> {
  data: T[];
  total: number;      // meta.totalMinistries | meta.totalMembers
}
```

### `services/ministryService.ts` (firma esperada)

```ts
const BASE = "/ministries";

export const ministryService = {
  list: (params?: { limit?: number; offset?: number }) =>
    http.getPaginated<Ministry>(BASE, params, "totalMinistries"),

  getById: (id: string) =>
    http.get<Ministry>(`${BASE}/${id}`),

  create: (dto: CreateMinistryDTO) =>
    http.post<Ministry>(BASE, dto),

  update: (id: string, dto: UpdateMinistryDTO) =>
    http.put<Ministry>(`${BASE}/${id}`, dto),

  remove: (id: string) =>
    http.delete<null>(`${BASE}/${id}`),

  listMembers: (id: string, params?: { limit?: number; offset?: number }) =>
    http.getPaginated<MinistryMember>(`${BASE}/${id}/users`, params, "totalMembers"),

  addMember: (ministryId: string, userId: string) =>
    http.post<null>(`${BASE}/${ministryId}/users/${userId}`),

  removeMember: (ministryId: string, userId: string) =>
    http.delete<null>(`${BASE}/${ministryId}/users/${userId}`),
};
```

> Si `httpClient` aún no expone `meta`, agregar un helper `getPaginated(url, params, metaKey)`
> que devuelva `{ data, total: meta?.[metaKey] ?? data.length }`. No romper la firma actual de `get`.

## 6. Requisitos funcionales

1. **Listado (`/ministries`):** visible para cualquier usuario autenticado.
   Tabla/grid con `nombre` y `descripcion` (truncada). Paginación server-side con `limit`/`offset`
   y total desde `meta.totalMinistries`. Botón **"Nuevo ministerio"** y acciones editar/eliminar
   **solo si `role === "ADMIN"`** (usar `useAuth()`); para el resto, la fila enlaza solo al detalle.
2. **Detalle (`/ministries/:id`):** muestra `nombre`, `descripcion` y la lista de miembros
   (`MinistryMembersList`, paginada con `meta.totalMembers`). Si es `ADMIN`: botones
   "Editar", "Eliminar", "Agregar miembro" y, por fila de miembro, "Quitar".
   `404` → pantalla "Ministerio no encontrado" con enlace de vuelta al listado.
3. **Crear (`/ministries/nuevo`):** `ProtectedRoute requiredRole="ADMIN"`. Formulario
   `nombre` (requerido, máx. 255, contador de caracteres) + `descripcion` (`textarea`, opcional).
   Validación en cliente antes de enviar. Éxito → redirigir al detalle del ministerio creado + toast.
4. **Editar (`/ministries/:id/editar`):** `ProtectedRoute requiredRole="ADMIN"`. Precarga con
   `getById`. Enviar en el `PUT` **solo los campos modificados** (`dirty fields`); si `descripcion`
   se vació, mandar `null`. Éxito → volver al detalle + toast.
5. **Eliminar:** `DeleteMinistryDialog` (modal de confirmación) que **advierte** que los usuarios
   asignados quedarán sin ministerio (no se eliminan). Éxito → redirigir a `/ministries`, refrescar y toast.
6. **Agregar miembro (`AddMemberDialog`, ADMIN):** selector/búsqueda de usuario alimentado por
   `userService.list()` (paginado; idealmente con filtro por nombre/correo del lado cliente sobre
   la página cargada, o cargando varias páginas). Al confirmar → `addMember`. Manejar:
   - `409` → toast "El usuario ya pertenece a este ministerio" (no es error bloqueante).
   - `404` "Usuario no encontrado" → refrescar la lista de usuarios.
   Éxito → cerrar diálogo, refrescar `useMinistryMembers`, toast.
7. **Quitar miembro (ADMIN):** confirmación inline o modal ligero → `removeMember`.
   `404` "El usuario no pertenece a este ministerio" → refrescar lista. Éxito → refrescar + toast.
8. **Manejo de errores:** reutilizar el componente global que renderiza `message` + `errors`
   del `ApiError`. `401` en cualquier request → `logout()` + redirect a `/login` (ya implementado
   en el interceptor del `httpClient`). `403` → toast + no romper la vista de lectura.
9. **Navegación:** agregar "Ministerios" al navbar/`AppShell` para todos los roles autenticados.

## 7. Rutas (router.tsx)

```tsx
// dentro del árbol privado (ProtectedRoute base = requiere sesión)
{ path: "ministries",            element: <MinistriesListPage /> },
{ path: "ministries/nuevo",      element: <ProtectedRoute requiredRole="ADMIN"><MinistryCreatePage /></ProtectedRoute> },
{ path: "ministries/:id",        element: <MinistryDetailPage /> },
{ path: "ministries/:id/editar", element: <ProtectedRoute requiredRole="ADMIN"><MinistryEditPage /></ProtectedRoute> },
```

> Definir la ruta `ministries/nuevo` **antes** de `ministries/:id` para que `"nuevo"` no se
> interprete como un id (con `react-router` 7 el orden de especificidad lo maneja, pero mantener
> el literal primero por claridad).

## 8. Requisitos no funcionales

- Todo llamado a la API pasa por `services/ministryService.ts` → `httpClient` (sin `fetch` suelto).
- Estados de carga y error explícitos en cada pantalla y en cada diálogo.
- Tipado estricto (`strict: true`), sin `any` en servicios ni hooks.
- Los `id` de la URL se tratan como `string`; no parsear a número.
- Reutilizar componentes de formulario/feedback existentes (inputs, toast, spinner, modal).
- Accesibilidad: `label` en cada campo, `aria-invalid`, foco en el primer error, `role="dialog"` en modales.
- Respetar el design system (clases semánticas: `bg-card`, `text-foreground`, `border-border`,
  `text-destructive`, `bg-primary`, `ring-ring`).
- Optimista opcional en asignar/quitar miembro, pero siempre con `refetch` de reconciliación.

## 9. Criterios de aceptación (verificable)

- [ ] Cualquier usuario autenticado puede ver el listado y el detalle de ministerios, y la lista de miembros.
- [ ] `PARTICIPANT`/`MEMBER` **no** ven botones de crear/editar/eliminar/administrar miembros;
      el acceso directo por URL a `/ministries/nuevo` o `/ministries/:id/editar` los bloquea (redirect/403).
- [ ] El listado pagina con `limit`/`offset` y muestra el total desde `meta.totalMinistries`.
- [ ] `ADMIN` crea un ministerio (`nombre` + `descripcion` opcional) y es redirigido a su detalle.
- [ ] `ADMIN` edita un ministerio enviando solo los campos modificados; vaciar `descripcion` la deja en `null`.
- [ ] Eliminar un ministerio pide confirmación, advierte del efecto sobre los miembros, y refresca el listado.
- [ ] La lista de miembros pagina con `meta.totalMembers`.
- [ ] `ADMIN` asigna un usuario; reintentar con el mismo usuario muestra el mensaje de `409` sin romper la UI.
- [ ] `ADMIN` quita un usuario del ministerio y la lista se refresca.
- [ ] Errores `401/403/404/409/422` se muestran con `message`/`errors` del envelope;
      `401` cierra sesión automáticamente.
- [ ] Ningún componente llama a `fetch` directo; todo pasa por `ministryService`.
```
