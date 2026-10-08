# Prompt — Integración Frontend: Autenticación y CRUD de Usuarios (Church Connect)

> Copia este bloque completo y pásalo a tu asistente de código (o úsalo como especificación de la tarea).
> Describe el contrato real del backend `Church-Connect-backend` (FastAPI) y la estructura que debe
> implementarse en `Church-Connect-Frontend` (React + Vite + TypeScript + TailwindCSS).

---

## 1. Objetivo

Implementar en el frontend el flujo completo de **registro**, **inicio de sesión** y **gestión de usuarios (CRUD)**
consumiendo la API REST del backend, respetando el control de acceso por roles y el formato de respuesta estándar.

## 2. Stack del frontend

- React 19 + Vite + TypeScript
- TailwindCSS v4
- `framer-motion` (animaciones), `lucide-react` (iconos)
- Cliente HTTP: `fetch` nativo envuelto en un módulo `httpClient` (o `axios` si se prefiere; mantener una sola capa)
- Routing: `react-router-dom` (agregar dependencia)
- Estado de sesión: React Context + `localStorage`

## 3. Configuración base de la API

| Concepto | Valor |
|---|---|
| Base URL (dev) | `http://localhost:8000` (configurable vía `VITE_API_URL`) |
| Prefijo global | `/api/v1` |
| Formato | JSON en request y response |
| Auth | `Authorization: Bearer <access_token>` en endpoints protegidos |
| Expiración token | 30 minutos (`ACCESS_TOKEN_EXPIRE_MINUTES`), algoritmo `HS256` |
| Payload del JWT | `{ "sub": "<uuid del usuario>", "rol": "ADMIN|PARTICIPANT|MEMBER", "exp": <timestamp> }` |

> **Nota CORS:** si el backend aún no tiene `CORSMiddleware` configurado, hay que agregarlo
> (`allow_origins` con el origen del frontend) o las peticiones desde el navegador fallarán.

## 4. Formato de respuesta estándar (`ResponsePayload`)

**Todas** las respuestas (éxito y error) tienen esta forma. Las claves van en **camelCase** por alias:

```json
{
  "statusCode": 200,
  "status": "OK",
  "data": { },
  "success": true,
  "message": "Mensaje descriptivo",
  "errors": null,
  "timestamp": "2026-08-31T12:00:00Z",
  "meta": null
}
```

- Éxito: `success: true`, `data` con el contenido, `errors: null`.
- Error: `success: false`, `data: null`, `errors: ["detalle", ...]`, `message` con resumen.
- Errores de validación (`422`): `message: "Error de validación en los datos enviados"`,
  `errors: ["body.campo: mensaje", ...]`.
- Paginación de listados: `meta.totalUsers` trae el conteo total real (independiente de `limit`/`offset`).

El `httpClient` del frontend debe **desempacar** `data` y, ante `success: false`, lanzar un error
tipado con `message` + `errors` para mostrarlo en la UI.

## 5. Modelo de Usuario

### `UserResponse` (lo que devuelve la API — nunca incluye `contrasena`)

| Campo | Tipo | Notas |
|---|---|---|
| `id` | `string` (UUID) | |
| `nombre` | `string` | |
| `apellido` | `string \| null` | |
| `correo` | `string` (email) | único |
| `telefono` | `string \| null` | |
| `rol` | `"ADMIN" \| "PARTICIPANT" \| "MEMBER"` | siempre en MAYÚSCULAS |
| `activo` | `boolean \| null` | |
| `fecha_creacion` | `string` (ISO datetime) \| null | |

### Roles

- `ADMIN`: acceso total a la gestión de usuarios.
- `PARTICIPANT` / `MEMBER`: solo su propio perfil.
- El registro público siempre crea usuarios con rol `MEMBER`.

## 6. Endpoints a consumir

### 6.1 Registro público — `POST /api/v1/auth/register`

- **Auth:** no requiere.
- **Body:**
  ```json
  { "nombre": "Ana", "apellido": "Pérez", "correo": "ana@mail.com", "contrasena": "secreta123", "telefono": "3001234567" }
  ```
  `telefono` es opcional. `nombre`, `apellido`, `correo`, `contrasena` obligatorios.
  `contrasena` debe tener entre 8 y 20 caracteres.
- **201:** `data` = `UserResponse` del usuario creado (rol `MEMBER`).
- **400:** correo ya registrado → `message: "El correo ya se encuentra registrado"`.
- **422:** campos faltantes o inválidos (incluye `contrasena` fuera del rango 8-20 caracteres).

### 6.2 Inicio de sesión — `POST /api/v1/auth/login`

- **Auth:** no requiere.
- **Body:** `{ "correo": "ana@mail.com", "contrasena": "secreta123" }`
- **200:** `data` = `{ "access_token": "<jwt>", "token_type": "bearer" }`
- **401:** `message: "Correo o contraseña incorrectos"` (no distingue cuál falló).
- Tras login: guardar token, decodificar `sub` y `rol`, y opcionalmente hacer
  `GET /api/v1/users/{sub}` para hidratar el perfil completo en el contexto.

### 6.3 Listar usuarios — `GET /api/v1/users`

- **Auth:** Bearer. **Solo `ADMIN`.**
- **Query:** `limit` (1–100, default 10), `offset` (>=0, default 0).
- **200:** `data` = `UserResponse[]`, `meta.totalUsers` = total.
- **401** sin token · **403** si no es `ADMIN`.

### 6.4 Obtener usuario por ID — `GET /api/v1/users/{id}`

- **Auth:** Bearer. `ADMIN` cualquier usuario; `PARTICIPANT`/`MEMBER` solo su propio `id`.
- **200:** `data` = `UserResponse`.
- **403** perfil ajeno sin ser admin · **404** `message: "Usuario no encontrado"`.

### 6.5 Crear usuario (con rol) — `POST /api/v1/users`

- **Auth:** Bearer. **Solo `ADMIN`.**
- **Body:** igual a register + `rol` (`ADMIN`/`PARTICIPANT`/`MEMBER`) y `activo` (bool, default `true`).
  El `rol` se normaliza a mayúsculas en el backend (`"admin"` → `"ADMIN"`).
- **201:** `data` = `UserResponse`.
- **400** correo duplicado · **403** no admin · **422** rol inválido / campos faltantes.

### 6.6 Actualizar usuario — `PUT /api/v1/users/{id}` (actualización parcial)

- **Auth:** Bearer. Solo se modifican los campos enviados en el body.
- **Body (todos opcionales):** `nombre`, `apellido`, `correo`, `contrasena`, `telefono`, `rol`, `activo`.
- Reglas de permisos:
  - `ADMIN`: puede actualizar cualquier usuario, incluidos `rol` y `activo`.
  - `PARTICIPANT`/`MEMBER`: solo su propio perfil y **no** pueden enviar `rol` ni `activo`
    (→ `403 "No tiene permisos para modificar el rol o el estado del usuario"`).
  - `contrasena`: cada usuario puede cambiar la suya propia; además `ADMIN` puede cambiar la
    de **cualquier** usuario. `PARTICIPANT`/`MEMBER` que intenten cambiar la de otro `id`
    reciben `403 "No tiene permisos para modificar la contraseña de otro usuario"`.
    Cuando se envía, debe tener entre 8 y 20 caracteres (si no, `422`).
- **200:** `data` = `UserResponse` actualizado · **400** correo en uso · **403** según reglas.

### 6.7 Eliminar usuario — `DELETE /api/v1/users/{id}`

- **Auth:** Bearer. **Solo `ADMIN`.**
- **200:** `data: null`, `message: "Usuario eliminado exitosamente"`.
- **403** no admin · **404** id inexistente.

### Matriz de permisos

| Acción | ADMIN | PARTICIPANT / MEMBER |
|---|---|---|
| Registro / Login | público | público |
| Listar usuarios | ✅ | ❌ 403 |
| Ver perfil propio | ✅ | ✅ |
| Ver perfil ajeno | ✅ | ❌ 403 |
| Crear usuario con rol | ✅ | ❌ 403 |
| Editar datos propios (no rol/activo) | ✅ | ✅ |
| Editar datos ajenos | ✅ | ❌ 403 |
| Editar rol/activo | ✅ | ❌ 403 |
| Editar contraseña propia | ✅ | ✅ |
| Editar contraseña ajena | ❌ 403 | ❌ 403 |
| Eliminar usuario | ✅ | ❌ 403 |

## 7. Estructura a implementar en el frontend

```
src/
├── config/
│   └── env.ts                 # VITE_API_URL, constantes
├── lib/
│   └── httpClient.ts          # fetch wrapper: base URL, headers, Bearer, desempaqueta ResponsePayload, maneja errores
├── types/
│   ├── api.ts                 # ResponsePayload<T>, ApiError
│   └── user.ts                # User, UserRole, CreateUserDTO, UpdateUserDTO, LoginDTO, RegisterDTO, TokenResponse
├── services/
│   ├── authService.ts         # register(), login()
│   └── userService.ts         # list(), getById(), create(), update(), remove()
├── auth/
│   ├── AuthContext.tsx        # { user, token, isAuthenticated, role, login(), register(), logout() }
│   ├── useAuth.ts             # hook de consumo del contexto
│   ├── jwt.ts                 # decodeJwt(), isExpired()
│   └── ProtectedRoute.tsx     # guard por autenticación y por rol (requiredRole?)
├── hooks/
│   ├── useUsers.ts            # listado + paginación (meta.totalUsers) + refetch
│   └── useUser.ts             # detalle por id
├── pages/
│   ├── auth/
│   │   ├── LoginPage.tsx
│   │   └── RegisterPage.tsx
│   ├── profile/
│   │   └── ProfilePage.tsx    # ver/editar perfil propio (incluye cambio de contraseña)
│   └── users/                 # solo ADMIN
│       ├── UsersListPage.tsx  # tabla + paginación + buscar + acciones
│       ├── UserCreatePage.tsx
│       └── UserEditPage.tsx   # editar datos, rol, activo
├── components/
│   ├── forms/                 # inputs, campo password con toggle, select de rol, switch activo
│   ├── feedback/              # Toast/Alert para message + errors, spinner
│   └── layout/                # AppShell, navbar con estado de sesión
└── router.tsx                 # rutas públicas (/login, /register) y privadas
```

### Contratos TypeScript sugeridos

```ts
export type UserRole = "ADMIN" | "PARTICIPANT" | "MEMBER";

export interface User {
  id: string;
  nombre: string;
  apellido: string | null;
  correo: string;
  telefono: string | null;
  rol: UserRole;
  activo: boolean | null;
  fecha_creacion: string | null;
}

export interface ResponsePayload<T> {
  statusCode: number;
  status: string | null;
  data: T | null;
  success: boolean;
  message: string | null;
  errors: string[] | null;
  timestamp: string;
  meta: Record<string, unknown> | null;
}

export interface LoginDTO { correo: string; contrasena: string; }
export interface RegisterDTO { nombre: string; apellido: string; correo: string; contrasena: string; telefono?: string; }
export interface TokenResponse { access_token: string; token_type: "bearer"; }
export interface CreateUserDTO extends RegisterDTO { rol: UserRole; activo?: boolean; }
export interface UpdateUserDTO {
  nombre?: string; apellido?: string; correo?: string;
  contrasena?: string; telefono?: string; rol?: UserRole; activo?: boolean;
}
```

## 8. Requisitos funcionales

1. **Registro:** formulario con `nombre`, `apellido`, `correo`, `contrasena` (+ confirmación local),
   `telefono` opcional. Validación en cliente antes de enviar. En éxito → redirigir a `/login` con mensaje.
   Mostrar error de correo duplicado (`400`) y de validación (`422`, mapear `errors` a cada campo).
2. **Login:** formulario `correo` + `contrasena`. En éxito: persistir `access_token`, decodificar JWT,
   cargar perfil (`GET /users/{sub}`), redirigir según rol (`ADMIN` → `/users`, resto → `/profile`).
   En `401` mostrar "Correo o contraseña incorrectos".
3. **Sesión:** `AuthContext` expone `user`, `role`, `isAuthenticated`. Token en `localStorage`
   (clave `cc_token`). Al montar la app, rehidratar sesión y verificar expiración (`exp`).
   Si el token expiró o cualquier request devuelve `401` → `logout()` + redirigir a `/login`.
4. **Guardas de ruta:** `ProtectedRoute` bloquea rutas privadas sin sesión; `requiredRole="ADMIN"`
   para la sección de usuarios (si no cumple → página 403 o redirección a `/profile`).
5. **Perfil propio (`/profile`):** ver datos, editar `nombre`/`apellido`/`correo`/`telefono`,
   sección aparte para cambiar contraseña (envía solo `contrasena` en el `PUT`). No mostrar campos `rol`/`activo`.
6. **Listado de usuarios (ADMIN):** tabla con paginación server-side usando `limit`/`offset` y
   `meta.totalUsers`; columnas nombre, correo, rol, activo, fecha; acciones ver/editar/eliminar.
7. **Crear usuario (ADMIN):** formulario completo con `select` de rol y `switch` de `activo`.
8. **Editar usuario (ADMIN):** permite cambiar `rol` y `activo`; **no** permite cambiar la contraseña
   de otro usuario (ocultar o deshabilitar ese campo salvo que el `id` sea el del propio admin).
9. **Eliminar usuario (ADMIN):** confirmación modal; en éxito refrescar listado y toast de éxito.
10. **Manejo de errores global:** componente que renderiza `message` y la lista `errors` del `ResponsePayload`.

## 9. Requisitos no funcionales

- Todos los llamados a la API pasan por `services/*` → `httpClient` (sin `fetch` suelto en componentes).
- Estados de carga y error explícitos en cada pantalla (nada de spinners infinitos).
- Accesibilidad básica en formularios (labels, `aria-invalid`, foco en el primer error).
- No almacenar la contraseña en estado global ni en logs.
- Tipado estricto (`strict: true`); sin `any` en la capa de servicios.
- Variables sensibles vía `.env` (`VITE_API_URL`), nunca hardcodeadas.

## 10. Criterios de aceptación (resumen verificable)

- [ ] Registro exitoso crea usuario `MEMBER` y redirige a login.
- [ ] Login guarda token, hidrata perfil y redirige según rol.
- [ ] Rutas privadas inaccesibles sin token; sección `/users` solo visible para `ADMIN`.
- [ ] Token expirado o `401` en cualquier request cierra sesión automáticamente.
- [ ] Listado de usuarios pagina con `limit`/`offset` y muestra el total desde `meta.totalUsers`.
- [ ] `ADMIN` puede crear (con rol), editar (incl. rol/activo) y eliminar usuarios.
- [ ] `MEMBER`/`PARTICIPANT` solo pueden ver y editar su propio perfil (sin rol/activo).
- [ ] Cambiar contraseña funciona solo sobre el perfil propio; el intento sobre otro devuelve 403 y se maneja en UI.
- [ ] Los mensajes de error (`400`, `401`, `403`, `404`, `422`) se muestran usando `message`/`errors` del envelope.
