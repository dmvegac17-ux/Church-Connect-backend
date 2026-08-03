# Historias de Usuario — Control de Acceso por Roles (Users)

Roles del sistema: `ADMIN`, `PARTICIPANT`, `MEMBER`.

---

## HU-01 — Registro público de usuarios

**Como** visitante no autenticado
**Quiero** poder crear mi propia cuenta
**Para** acceder a la plataforma sin depender de un administrador

**Endpoint:** `POST /api/v1/auth/register`

### Criterios de aceptación

1. **Dado** que no estoy autenticado, **cuando** envío `nombre`, `apellido`, `correo`, `contrasena` y `telefono` válidos, **entonces** recibo `201` y el usuario se crea con `rol = MEMBER` sin importar si no se envía `rol` en el body (el campo no existe en este endpoint).
2. **Dado** un registro exitoso, **cuando** reviso la respuesta, **entonces** `success = true` y `data` contiene el usuario creado sin el campo `contrasena`.
3. **Dado** que `nombre` o `apellido` no se envían (o van vacíos), **cuando** intento registrarme, **entonces** recibo `422` con el detalle del campo faltante.
4. **Dado** un `correo` ya registrado previamente, **cuando** intento registrarme con ese mismo correo, **entonces** recibo `400` con mensaje "El correo ya se encuentra registrado".
5. **Dado** un registro exitoso, **cuando** consulto la base de datos, **entonces** la `contrasena` almacenada está hasheada (bcrypt), nunca en texto plano.

---

## HU-02 — Inicio de sesión

**Como** usuario registrado (cualquier rol)
**Quiero** autenticarme con correo y contraseña
**Para** obtener un token de acceso y usar endpoints protegidos

**Endpoint:** `POST /api/v1/auth/login`

### Criterios de aceptación

1. **Dado** credenciales correctas, **cuando** hago login, **entonces** recibo `200` con `data.access_token` (JWT) y `data.token_type = "bearer"`.
2. **Dado** un correo inexistente o contraseña incorrecta, **cuando** intento login, **entonces** recibo `401` con mensaje "Correo o contraseña incorrectos" (sin distinguir cuál de los dos falló, por seguridad).
3. **Dado** un token obtenido, **cuando** lo uso en el header `Authorization: Bearer <token>`, **entonces** el sistema me identifica como el usuario correspondiente en cualquier endpoint protegido.

---

## HU-03 — Listar todos los usuarios (solo ADMIN)

**Como** administrador
**Quiero** listar todos los usuarios del sistema
**Para** gestionar la plataforma

**Endpoint:** `GET /api/v1/users`

### Criterios de aceptación

1. **Dado** un usuario con rol `ADMIN` autenticado, **cuando** consulta `GET /users`, **entonces** recibo `200` con `data` (lista de usuarios) y `meta.totalUsers` (conteo total, independiente de paginación).
2. **Dado** un usuario con rol `PARTICIPANT` o `MEMBER` autenticado, **cuando** intenta consultar `GET /users`, **entonces** recibe `403` con mensaje "No tiene permisos para realizar esta acción".
3. **Dado** ningún token enviado, **cuando** se consulta `GET /users`, **entonces** recibo `401` con mensaje "Not authenticated".
4. **Dado** los parámetros `limit` y `offset`, **cuando** se consulta con `limit=2`, **entonces** `data` contiene máximo 2 elementos, pero `meta.totalUsers` refleja el total real de usuarios en la tabla (no solo los devueltos).

---

## HU-04 — Consultar un usuario por ID

**Como** usuario autenticado (cualquier rol)
**Quiero** consultar el detalle de un usuario
**Para** ver su información

**Endpoint:** `GET /api/v1/users/{id}`

### Criterios de aceptación

1. **Dado** un usuario `ADMIN`, **cuando** consulta el `id` de **cualquier** otro usuario, **entonces** recibe `200` con los datos de ese usuario.
2. **Dado** un usuario `PARTICIPANT` o `MEMBER`, **cuando** consulta **su propio** `id`, **entonces** recibe `200` con sus propios datos.
3. **Dado** un usuario `PARTICIPANT` o `MEMBER`, **cuando** consulta el `id` de **otro** usuario distinto al suyo, **entonces** recibe `403`.
4. **Dado** un `id` que no existe en la base de datos, **cuando** un `ADMIN` lo consulta, **entonces** recibe `404` con mensaje "Usuario no encontrado".

---

## HU-05 — Crear usuario con rol específico (solo ADMIN)

**Como** administrador
**Quiero** crear usuarios asignando directamente su rol (`ADMIN`, `PARTICIPANT` o `MEMBER`)
**Para** dar de alta cuentas con privilegios específicos sin pasar por el registro público

**Endpoint:** `POST /api/v1/users`

### Criterios de aceptación

1. **Dado** un usuario `ADMIN` autenticado, **cuando** envía `nombre`, `apellido`, `correo`, `contrasena`, `telefono` y `rol`, **entonces** recibe `201` y el usuario se crea con el `rol` indicado (incluyendo `ADMIN`).
2. **Dado** un usuario `PARTICIPANT` o `MEMBER` autenticado, **cuando** intenta crear un usuario, **entonces** recibe `403`.
3. **Dado** un `rol` enviado en minúsculas o mixto (`"admin"`, `"Admin"`), **cuando** se crea el usuario, **entonces** se normaliza y almacena en mayúsculas (`"ADMIN"`).
4. **Dado** un `rol` con un valor fuera de `ADMIN`/`PARTICIPANT`/`MEMBER` (ej. `"superadmin"`), **cuando** se intenta crear, **entonces** recibe `422`.
5. **Dado** `nombre` o `apellido` ausentes, **cuando** se intenta crear, **entonces** recibe `422`.
6. **Dado** un `correo` ya registrado, **cuando** se intenta crear, **entonces** recibe `400`.

---

## HU-06 — Actualizar usuario

**Como** usuario autenticado
**Quiero** actualizar datos de un perfil, con restricciones según mi rol
**Para** mantener la información al día sin comprometer la seguridad de otras cuentas

**Endpoint:** `PUT /api/v1/users/{id}` *(comportamiento de actualización parcial — solo se modifican los campos enviados en el body)*

### Criterios de aceptación

1. **Dado** un usuario `ADMIN`, **cuando** actualiza cualquier campo (incluyendo `rol` y `activo`) de **cualquier** usuario, **entonces** recibe `200` con los datos actualizados.
2. **Dado** un usuario `PARTICIPANT` o `MEMBER`, **cuando** actualiza campos de **su propio** perfil que **no sean** `rol` ni `activo` (ej. `nombre`, `telefono`), **entonces** recibe `200`.
3. **Dado** un usuario `PARTICIPANT` o `MEMBER`, **cuando** intenta enviar `rol` y/o `activo` en el body (así sea sobre su propio perfil), **entonces** recibe `403` con mensaje "No tiene permisos para modificar el rol o el estado del usuario", y ningún campo se actualiza.
4. **Dado** cualquier usuario autenticado, **cuando** intenta actualizar el perfil de **otro** usuario que no sea el suyo y no es `ADMIN`, **entonces** recibe `403`.
5. **Dado** cualquier usuario (incluido `ADMIN`), **cuando** envía el campo `contrasena` en el body de actualización de un `id` que **no es el suyo**, **entonces** recibe `403` con mensaje "No tiene permisos para modificar la contraseña de otro usuario" — **sin excepción para `ADMIN`**.
6. **Dado** cualquier usuario, **cuando** envía `contrasena` para actualizar **su propio** perfil, **entonces** recibe `200` y la contraseña se actualiza (hasheada).
7. **Dado** un body que solo contiene `{"apellido": "Nuevo"}`, **cuando** se envía, **entonces** solo se actualiza `apellido`; el resto de campos (`nombre`, `correo`, `telefono`, `rol`, `activo`, `contrasena`) permanece sin cambios.
8. **Dado** un `correo` que ya pertenece a otro usuario, **cuando** se intenta actualizar a ese correo, **entonces** recibe `400`.

---

## HU-07 — Eliminar usuario (solo ADMIN)

**Como** administrador
**Quiero** eliminar cuentas de usuario
**Para** dar de baja usuarios de la plataforma

**Endpoint:** `DELETE /api/v1/users/{id}`

### Criterios de aceptación

1. **Dado** un usuario `ADMIN` autenticado, **cuando** elimina un `id` existente, **entonces** recibe `200` con `success = true` y mensaje "Usuario eliminado exitosamente".
2. **Dado** un usuario `PARTICIPANT` o `MEMBER`, **cuando** intenta eliminar cualquier usuario (incluido su propio `id`), **entonces** recibe `403`.
3. **Dado** un `id` inexistente, **cuando** un `ADMIN` intenta eliminarlo, **entonces** recibe `404`.
4. **Dado** un usuario recién eliminado, **cuando** se intenta hacer login con sus credenciales, **entonces** recibe `401`.

---

## Matriz resumen de permisos (para referencia rápida del QA)

| Acción | ADMIN | PARTICIPANT | MEMBER |
|---|---|---|---|
| Registrarse (`/auth/register`) | — (público, sin rol) | — (público, sin rol) | — (público, sin rol) |
| Listar usuarios | ✅ | ❌ 403 | ❌ 403 |
| Ver perfil propio | ✅ | ✅ | ✅ |
| Ver perfil ajeno | ✅ | ❌ 403 | ❌ 403 |
| Crear usuario (con rol) | ✅ | ❌ 403 | ❌ 403 |
| Actualizar datos propios (excepto rol/activo) | ✅ | ✅ | ✅ |
| Actualizar datos ajenos (excepto rol/activo) | ✅ | ❌ 403 | ❌ 403 |
| Actualizar `rol`/`activo` propio o ajeno | ✅ | ❌ 403 | ❌ 403 |
| Actualizar `contrasena` propia | ✅ | ✅ | ✅ |
| Actualizar `contrasena` ajena | ❌ 403 | ❌ 403 | ❌ 403 |
| Eliminar usuario (propio o ajeno) | ✅ | ❌ 403 | ❌ 403 |

**Notas para QA:**
- Todos los endpoints protegidos, sin token, devuelven `401` con `message: "Not authenticated"`.
- Todas las respuestas siguen el formato `ResponsePayload`: `statusCode`, `status`, `data`, `success`, `message`, `errors`, `timestamp`, `meta`.
- El rol se normaliza a mayúsculas independientemente de cómo se envíe en el request (`admin` → `ADMIN`).
