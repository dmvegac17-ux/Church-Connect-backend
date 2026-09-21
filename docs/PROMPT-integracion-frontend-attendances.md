# Prompt — Integración Frontend: Asistencias (Church Connect)

> Copia este bloque completo y pásalo a tu asistente de código (o úsalo como especificación de la tarea).
> Describe el contrato real del backend `Church-Connect-backend` (FastAPI) para el módulo
> **Asistencias** (`attendances`) — CRUD completo — y la estructura que debe implementarse en
> `Church-Connect-Frontend` (React 19 + Vite + TypeScript + TailwindCSS v4 + react-router-dom 7).
>
> **Depende de** la integración de autenticación ya implementada (`lib/httpClient.ts`,
> `auth/AuthContext`, `ProtectedRoute`, el envelope `ResponsePayload<T>`, el token en
> `localStorage` vía `TOKEN_STORAGE_KEY`) y de los módulos de **Usuarios** (`userService`) y
> **Eventos** (`eventService`) ya integrados: Asistencias los referencia por `usuario_id` /
> `evento_id` y no trae los objetos anidados, así que hay que resolver nombres con esos
> servicios. Este documento **solo agrega** el módulo de asistencias.

---

## 1. Objetivo

Implementar en el frontend un **CRUD completo de asistencias** para uso exclusivo de `ADMIN`:
registrar si un usuario asistió (o no) a un evento, listar/filtrar el historial, editarlo y
eliminarlo. **No existe una vista de autoservicio** ("mi asistencia") — a diferencia de
Notificaciones, aquí ningún rol distinto de `ADMIN` puede ver ni su propia asistencia por este
módulo.

## 2. Configuración base de la API

| Concepto | Valor |
|---|---|
| Base URL (dev) | `http://localhost:8000` (`VITE_API_URL`) |
| Prefijo global | `/api/v1` |
| Prefijo del módulo | `/attendances` |
| Auth | `Authorization: Bearer <access_token>` en **todos** los endpoints |
| Formato | JSON en request y response |

Todas las respuestas usan el envelope `ResponsePayload<T>` ya tipado en `types/api.ts`
(`statusCode`, `status`, `data`, `success`, `message`, `errors`, `timestamp`, `meta`). El
`httpClient` ya desempaca `data`/`meta` y lanza `ApiError` (con `message` + `errors` + `status`)
ante `success: false` o HTTP no-2xx — reutilízalo tal cual, no hace falta ningún ajuste especial
(a diferencia del envío masivo de notificaciones, aquí no hay statuses "de negocio" fuera de 2xx).

- Paginación del listado: `meta.totalAttendances` trae el conteo total (respetando los filtros
  `usuario_id`/`evento_id` si se enviaron), independiente de `limit`/`offset`.
- Validación (`422`): `message: "Error de validación en los datos enviados"`,
  `errors: ["body.campo: mensaje", ...]`.

## 3. Modelo de datos

### `Attendance` — `AttendanceResponse` (lo que devuelve la API)

| Campo | Tipo | Notas |
|---|---|---|
| `id` | `string` (UUID) | |
| `usuario_id` | `string` (UUID) \| `null` | destinatario de la asistencia |
| `evento_id` | `string` (UUID) \| `null` | evento asistido |
| `asistio` | `boolean` \| `null` | `true`/`false` explícito, no un flag de presencia |
| `fecha_registro` | `string` (ISO datetime) \| `null` | asignada por el servidor al crear, no editable |
| `publicado_por` | `string` (UUID) | id del `ADMIN` que registró la asistencia (tomado del token, **no editable**) |

> **Nulabilidad "de esquema" vs. real:** el backend declara `usuario_id`, `evento_id`,
> `asistio` y `fecha_registro` como opcionales en el modelo de respuesta, pero **en la práctica
> siempre vienen presentes** tras un `create` exitoso (el backend los exige al crear y no hay
> forma de vaciarlos después). Tipa la interfaz TS como el backend la declara (`| null`) para no
> romper si algún registro legado los trae vacíos, pero no bloquees la UI esperando que falten en
> el flujo normal.

> **Sin datos anidados:** la respuesta **no** incluye el objeto `usuario` ni `evento`, solo sus
> `id`. Para mostrar nombres en las tablas/formularios hay que cruzar con `userService` y
> `eventService` (ver §5 y §7) — no asumas que el backend los va a embeber más adelante.

## 4. Endpoints a consumir

Todos cuelgan de `/api/v1/attendances`. Todos requieren `Authorization: Bearer <token>` **y**
rol `ADMIN`. Sin token → `401`. Cualquier otro rol → `403 "No tiene permisos para realizar esta acción"`.

### 4.1 Listar asistencias — `GET /api/v1/attendances`

- **Auth:** solo `ADMIN`.
- **Query:** `limit` (1–100, default `10`), `offset` (>= 0, default `0`), `usuario_id` (UUID,
  opcional), `evento_id` (UUID, opcional). Ambos filtros son combinables (AND).
- **200:** `data` = `AttendanceResponse[]`, `meta.totalAttendances` = total con los mismos filtros
  aplicados. `message: "Asistencias obtenidas exitosamente"`.

### 4.2 Obtener asistencia por ID — `GET /api/v1/attendances/{attendance_id}`

- **Auth:** solo `ADMIN`.
- **200:** `data` = `AttendanceResponse`. `message: "Asistencia obtenida exitosamente"`.
- **404:** `"Asistencia no encontrada"`.
- **422:** `attendance_id` no es un UUID válido.

### 4.3 Registrar asistencia — `POST /api/v1/attendances`

- **Auth:** solo `ADMIN`.
- **Body:**
  ```json
  { "usuario_id": "d96d095e-0a9b-4f98-b89d-0e63afc6e08e", "evento_id": "1c2b3a4d-5e6f-4a1b-8c9d-0e1f2a3b4c5d", "asistio": true }
  ```
- **201:** `data` = `AttendanceResponse` creada (`publicado_por` = id del admin autenticado,
  `fecha_registro` = ahora). `message: "Asistencia registrada exitosamente"`.
- **404:** `"Usuario no encontrado"` **o** `"Evento no encontrado"` (según cuál de los dos IDs no exista).
- **409:** `"Ya existe una asistencia registrada para este usuario en este evento"` — la pareja
  `(usuario_id, evento_id)` es única; para corregir un registro existente hay que **editarlo**
  (§4.4), no crear uno nuevo.
- **422:** campos inválidos/faltantes.

### 4.4 Actualizar asistencia — `PUT /api/v1/attendances/{attendance_id}` (parcial)

- **Auth:** solo `ADMIN`.
- **Body (todos opcionales, se actualiza solo lo enviado):**
  ```json
  { "asistio": false }
  ```
  `usuario_id`/`evento_id` **sí son editables** aquí (a diferencia de Notificaciones) — permite
  reasignar un registro mal capturado. `publicado_por` y `fecha_registro` **no** son editables
  (no están en el schema de entrada).
- **200:** `data` = `AttendanceResponse` actualizada. `message: "Asistencia actualizada exitosamente"`.
- **404:** `"Asistencia no encontrada"` (el id de la URL no existe) **o** `"Usuario no encontrado"`/`"Evento no encontrado"`
  (si se envía un `usuario_id`/`evento_id` que reemplaza al actual y no existe).
- **409:** mismo mensaje que en creación, si el nuevo par `(usuario_id, evento_id)` ya
  pertenece a **otra** asistencia.
- **422:** campos inválidos.

### 4.5 Eliminar asistencia — `DELETE /api/v1/attendances/{attendance_id}`

- **Auth:** solo `ADMIN`.
- **200:** `data: null`, `message: "Asistencia eliminada exitosamente"`.
- **404:** `"Asistencia no encontrada"`.

### Matriz de permisos

| Acción | ADMIN | PARTICIPANT / MEMBER | Sin token |
|---|---|---|---|
| Listar / ver detalle | ✅ | ❌ 403 | ❌ 401 |
| Crear | ✅ | ❌ 403 | ❌ 401 |
| Editar | ✅ | ❌ 403 | ❌ 401 |
| Eliminar | ✅ | ❌ 403 | ❌ 401 |

> No hay ningún endpoint de "mi asistencia" para roles no-`ADMIN`. Si el producto lo necesita
> más adelante, es un endpoint nuevo a pedir al backend — no lo simules filtrando en el cliente
> (un `PARTICIPANT`/`MEMBER` ni siquiera puede llamar a `GET /attendances`).

## 5. Estructura a implementar en el frontend

Sigue el mismo patrón ya usado en `services/eventService.ts` / `services/userService.ts`
(`httpClient.get/post/put/delete` + `readMetaTotal`, **no** el `postRaw` especial de
notificaciones — aquí no hace falta):

```
src/
├── types/
│   └── attendance.ts          # Attendance, CreateAttendanceDTO, UpdateAttendanceDTO
├── services/
│   └── attendanceService.ts   # list, getById, create, update, remove
├── hooks/
│   ├── useAttendances.ts      # listado + filtros (usuario_id/evento_id) + paginación + refetch
│   └── useAttendance.ts       # detalle por id
├── pages/
│   └── attendances/
│       ├── AttendancesListPage.tsx   # ADMIN: tabla con filtros por usuario/evento
│       ├── AttendanceCreatePage.tsx  # ADMIN: selecciona usuario + evento + asistio
│       ├── AttendanceEditPage.tsx    # ADMIN: edición parcial
│       └── components/
│           ├── AttendanceForm.tsx        # compartido create/edit: <select> usuario (userService.list),
│           │                             # <select> evento (eventService.list), checkbox/toggle asistio
│           └── AttendanceFilters.tsx     # filtros de usuario/evento sobre el listado
└── router.tsx                 # + rutas de asistencias (ver §8)
```

### Contratos TypeScript

```ts
// types/attendance.ts

/** `AttendanceResponse` — lo que devuelve la API para una asistencia. */
export interface Attendance {
  id: string;
  usuario_id: string | null;
  evento_id: string | null;
  asistio: boolean | null;
  /** ISO datetime, asignada por el servidor. */
  fecha_registro: string | null;
  /** id (UUID) del ADMIN que la registró. */
  publicado_por: string;
}

/** Cuerpo de `POST /attendances`. */
export interface CreateAttendanceDTO {
  usuario_id: string;
  evento_id: string;
  asistio: boolean;
}

/** Cuerpo de `PUT /attendances/{id}` — actualización parcial. */
export interface UpdateAttendanceDTO {
  usuario_id?: string;
  evento_id?: string;
  asistio?: boolean;
}
```

### `services/attendanceService.ts` (firma esperada)

```ts
import { httpClient, readMetaTotal } from "../lib/httpClient";
import type { Attendance, CreateAttendanceDTO, UpdateAttendanceDTO } from "../types/attendance";

const BASE = "/attendances";

export interface ListAttendancesParams {
  limit?: number;
  offset?: number;
  usuario_id?: string;
  evento_id?: string;
  signal?: AbortSignal;
}

export interface PaginatedAttendances {
  items: Attendance[];
  total: number;
}

/** `GET /attendances` — solo ADMIN. Paginación server-side + filtros opcionales. */
async function list({
  limit = 10,
  offset = 0,
  usuario_id,
  evento_id,
  signal,
}: ListAttendancesParams = {}): Promise<PaginatedAttendances> {
  const { data, meta } = await httpClient.get<Attendance[]>(BASE, {
    query: { limit, offset, usuario_id, evento_id },
    signal,
  });
  return {
    items: data ?? [],
    total: readMetaTotal(meta, "totalAttendances"),
  };
}

/** `GET /attendances/{id}` — solo ADMIN. `404` si no existe. */
async function getById(id: string, signal?: AbortSignal): Promise<Attendance> {
  const { data } = await httpClient.get<Attendance>(`${BASE}/${id}`, { signal });
  return data;
}

/** `POST /attendances` — solo ADMIN. `409` si el par usuario/evento ya existe. */
async function create(dto: CreateAttendanceDTO): Promise<Attendance> {
  const { data } = await httpClient.post<Attendance>(BASE, dto);
  return data;
}

/** `PUT /attendances/{id}` — solo ADMIN. Actualización parcial. */
async function update(id: string, dto: UpdateAttendanceDTO): Promise<Attendance> {
  const { data } = await httpClient.put<Attendance>(`${BASE}/${id}`, dto);
  return data;
}

/** `DELETE /attendances/{id}` — solo ADMIN. */
async function remove(id: string): Promise<void> {
  await httpClient.delete<null>(`${BASE}/${id}`);
}

export const attendanceService = { list, getById, create, update, remove };
```

## 6. Resolución de nombres (usuario/evento)

Como `AttendanceResponse` solo trae IDs, la tabla de listado y el formulario necesitan:

- **Formulario (crear/editar):** dos `<select>` poblados con `userService.list({ limit: 100 })` y
  `eventService.list({ limit: 100 })` (o un combobox con búsqueda si las listas crecen mucho —
  reutiliza el patrón que ya exista para seleccionar usuario en otros módulos, p. ej. el selector
  de destinatario de `NotificationForm.tsx` si aplica).
- **Tabla de listado:** para no hacer N+1 requests, cargar de antemano un `Map<string, User>` y
  `Map<string, Event>` (a partir de los mismos `list()` con un `limit` suficientemente alto, o
  cachear con `getById` bajo demanda si el volumen de asistencias es bajo) y resolver
  `usuario_id`/`evento_id` a `nombre`/`titulo` en el render. Si el id no está en el mapa (usuario o
  evento borrado después de registrar la asistencia), mostrar el UUID crudo o "Usuario eliminado" /
  "Evento eliminado" en vez de romper la fila.

## 7. Requisitos funcionales

1. **Listado (`/attendances`):** `ProtectedRoute requiredRole="ADMIN"`. Tabla paginada
   (`limit`/`offset`, total desde `meta.totalAttendances`) con columnas: usuario (nombre
   resuelto), evento (título resuelto), `asistio` (badge Sí/No), `fecha_registro` (formateada).
   Filtros por usuario y/o evento (`AttendanceFilters`) que se traducen en los query params
   `usuario_id`/`evento_id`; al cambiar un filtro, resetear `offset` a `0`.
2. **Crear (`AttendanceCreatePage`):** formulario con selector de usuario, selector de evento y
   toggle/checkbox `asistio` (default `true`, ya que lo más común es registrar asistencia
   confirmada; permitir marcarlo en `false` para dejar constancia de una inasistencia esperada).
   - Éxito (`201`) → toast + redirigir al listado (o al detalle si existe).
   - `409` → mostrar el error inline junto a los selectores ("Ya existe una asistencia registrada
     para este usuario en este evento") y **no** limpiar el formulario, para que el admin pueda
     corregir o navegar a editar el registro existente.
   - `404` (usuario o evento ya no existe, p. ej. borrado entre que se cargó el `<select>` y el
     submit) → toast de error + refrescar las listas de usuarios/eventos.
3. **Editar (`AttendanceEditPage`):** mismo formulario que crear, precargado con
   `getById`, enviando solo los campos modificados (`exclude_unset` en el backend). Mismo manejo
   de `409`/`404` que en creación.
4. **Eliminar:** botón de confirmación (modal) desde la tabla o el detalle; en éxito, refrescar
   el listado y mostrar toast.
5. **Manejo de errores:** reutilizar el componente global que renderiza `message`/`errors` del
   `ApiError` para `404/422`. `401` → `logout()` + redirect a `/login` (ya lo hace el interceptor
   del `httpClient`). `403` (rol insuficiente, p. ej. acceso directo por URL) → redirigir a `/403`
   (ya existe `ForbiddenPage`, mismo patrón que usa `ProtectedRoute` en el resto de rutas admin).
6. **Navegación:** agregar "Asistencias" al navbar/`AppShell` **solo visible para `ADMIN`**
   (a diferencia de Eventos/Ministerios/Notificaciones, que sí muestran enlace de lectura a todos).

## 8. Rutas (router.tsx)

Sigue la convención en español ya usada por Eventos/Ministerios/Cronogramas (`nuevo`/`editar`),
no la inglesa de Usuarios/Notificaciones — Asistencias es un módulo nuevo, se alinea con el
patrón más reciente:

```tsx
// dentro del árbol privado (ProtectedRoute base = requiere sesión), junto a las demás rutas admin
<Route
  path="/attendances"
  element={
    <ProtectedRoute requiredRole="ADMIN">
      <AttendancesListPage />
    </ProtectedRoute>
  }
/>
<Route
  path="/attendances/nueva"
  element={
    <ProtectedRoute requiredRole="ADMIN">
      <AttendanceCreatePage />
    </ProtectedRoute>
  }
/>
<Route
  path="/attendances/:id/editar"
  element={
    <ProtectedRoute requiredRole="ADMIN">
      <AttendanceEditPage />
    </ProtectedRoute>
  }
/>
```

> Definir `attendances/nueva` **antes** de cualquier ruta `attendances/:id` que llegues a agregar
> (p. ej. un futuro detalle), para que `"nueva"` no se interprete como un id — mismo cuidado que
> ya se tomó en Eventos/Ministerios/Notificaciones.

## 9. Requisitos no funcionales

- Todo llamado a la API pasa por `services/attendanceService.ts` → `httpClient` (sin `fetch` suelto).
- Estados de carga y error explícitos en cada pantalla (listado, formulario, resolución de
  nombres usuario/evento).
- Tipado estricto (`strict: true`), sin `any` en servicios ni hooks.
- Los `id` de la URL y de los `<select>` se tratan como `string`; no parsear a número.
- Reutilizar componentes de formulario/feedback existentes (inputs, `<select>`, toast, spinner,
  modal de confirmación de borrado).
- Accesibilidad: `label` en cada campo (incluyendo los `<select>` de usuario/evento), `aria-invalid`,
  foco en el primer error.
- Respetar el design system (clases semánticas: `bg-card`, `text-foreground`, `border-border`,
  `text-destructive`, `bg-primary`, `ring-ring`).

## 10. Criterios de aceptación (verificable)

- [ ] `PARTICIPANT`/`MEMBER` no ven el enlace "Asistencias"; el acceso directo por URL a
      `/attendances` (o cualquier subruta) los redirige a `/403`.
- [ ] `ADMIN` ve el listado paginado con `meta.totalAttendances`, con nombres de usuario/evento
      resueltos (no UUIDs crudos) en cada fila.
- [ ] Filtrar por usuario y/o evento actualiza la tabla y resetea la paginación a la primera página.
- [ ] Crear una asistencia con un par `(usuario, evento)` nuevo → `201`, toast de éxito, aparece
      en el listado.
- [ ] Crear una asistencia repitiendo un par `(usuario, evento)` ya existente → `409` mostrado
      inline, el formulario no se limpia.
- [ ] Editar `asistio` de un registro existente → `200`, el cambio se refleja en el listado.
- [ ] Editar el `usuario_id`/`evento_id` de un registro hacia un par que ya pertenece a otra
      asistencia → `409` mostrado inline.
- [ ] Eliminar una asistencia pide confirmación y, tras confirmar, desaparece del listado.
- [ ] Errores `401/403/404/409/422` se muestran con `message`/`errors` del envelope; `401` cierra
      sesión automáticamente.
- [ ] Ningún componente llama a `fetch` directo; todo pasa por `attendanceService`.
