# Usuarios y perfiles

La información de una persona está en dos tablas, uno a uno:

| Tabla | Qué guarda |
|---|---|
| `usuarios` | La cuenta: correo, contraseña (hash), rol, si está activa, fechas de acceso y seguridad. |
| `perfiles` | Los datos personales: nombre, apellido, teléfono y los que se agreguen. |

- `perfiles.usuario_id` es a la vez clave primaria y referencia a `usuarios.id`: un perfil por cuenta. Al eliminar el usuario se elimina su perfil.
- Las demás tablas (inscripciones, invitaciones, notificaciones…) siguen apuntando a `usuarios`.
- El perfil se crea junto con la cuenta, en la misma transacción: al asignar `usuario.nombre` por primera vez (`UserModel._perfil`). No hay trigger en la base.
- El perfil llega siempre con el usuario, en la misma consulta (`lazy="joined"`).
- En el código, `usuario.nombre`, `usuario.apellido` y `usuario.telefono` se leen y escriben igual que antes; `UserModel` los guarda en el perfil.

## Quién puede ver qué

Lo decide la API, no la base de datos:

- Cada persona ve y edita su propio perfil (`GET` / `PUT /users/{id}` con su id).
- El administrador ve y edita los de todos, y es el único que puede listarlos.
- Un miembro no puede consultar el perfil de otro. De los demás solo ve el nombre, donde la aplicación lo muestra (responsables confirmados, integrantes de un ministerio).

La seguridad por filas de Supabase está activada en `perfiles`, sin políticas: así la API pública de Supabase no puede leerla. El backend se conecta como dueño y no se ve afectado.

## Agregar un dato nuevo al perfil

Ejemplo: fecha de nacimiento. No se toca `usuarios`.

1. **Modelo**: una columna en `PerfilModel` (`src/infrastructure/database/models/perfil_model.py`).

   ```python
   fecha_nacimiento: Mapped[date | None] = mapped_column(Date, nullable=True)
   ```

2. **Acceso desde el usuario**: una propiedad en `UserModel`, igual que `telefono` (lectura, escritura y expresión SQL).
3. **Migración**: `alembic revision -m "fecha de nacimiento"` con `op.add_column("perfiles", ...)`. Siempre opcional (`nullable=True`), para que los perfiles existentes sigan valiendo.
4. **Validación**: el campo en `UserUpdate` y `UserResponse` (`src/api/v1/users/schemas.py`), con sus reglas. Si es un dato privado, no se agrega a las respuestas que ven otros miembros.
5. **Formulario**: el campo en la pantalla de perfil del frontend (`src/pages/profile/ProfilePage.tsx`) y en el tipo `User`.
6. **Prueba**: un caso en `tests/test_perfiles.py`.
