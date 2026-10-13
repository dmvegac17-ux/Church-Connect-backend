# Mejoras de Eventos y Cronograma — Validaciones, Mapa y UX

> Entregable: (1) criterios de aceptación en formato Dado/Cuando/Entonces para las 4 áreas
> solicitadas, y (2) la especificación técnica de las validaciones de backend/base de datos que
> las respaldan. Es una extensión de lo ya implementado (tarjetas de evento + modal de
> cronograma, ver `docs/PROMPT-integracion-frontend-eventos-cronograma.md`); **no** reemplaza
> ese documento, lo complementa. Nada de lo descrito aquí está implementado todavía — es la
> especificación para la siguiente iteración.

---

## Parte 1 — Criterios de aceptación

### 1. Validaciones de negocio y seguridad

#### Criterio 1.1 — El botón "Guardar cronograma" solo se habilita con el formulario válido

- **Dado** que el modal de cronograma tiene al menos una fila con un campo obligatorio vacío,
  con un horario inválido (`hora_fin <= hora_inicio`), fuera del rango del evento, o solapado
  con otra actividad,
- **Cuando** el usuario mira el botón "Guardar cronograma",
- **Entonces** el botón se renderiza `disabled` (estilo atenuado, `cursor-not-allowed`) y no
  dispara ninguna petición al backend.

- **Dado** que todas las filas quedan completas y sin errores de validación,
- **Cuando** el estado de validación se recalcula tras cada cambio (agregar, editar, eliminar o
  reordenar una fila),
- **Entonces** el botón se habilita automáticamente, sin recargar la página.

#### Criterio 1.2 — El backend rechaza datos inválidos aunque el frontend sea manipulado

- **Dado** que alguien abre las herramientas de desarrollador y fuerza el envío de un
  `POST`/`PUT /schedules` (o `/events`) con campos obligatorios vacíos, nulos, de tipo inválido,
  o saltándose la restricción visual del botón deshabilitado,
- **Cuando** la petición llega a la API,
- **Entonces** el backend la rechaza — `422` si el problema es de esquema (campo faltante,
  vacío o fuera de los límites de longitud) o `400` si el problema es una regla de negocio
  (fechas invertidas, fuera del rango del evento, solape) — **nunca** `200`/`201`, y el mensaje
  identifica el campo o la regla que falló.
- **Y** la base de datos actúa como última línea de defensa: si por cualquier vía una fila
  inválida llegara a un `INSERT`/`UPDATE`, la restricción de columna/`CHECK` correspondiente
  rechaza la operación en vez de persistir el dato.

### 2. Lógica y consistencia de fechas/horas (Eventos)

#### Criterio 2.1 — El evento no puede terminar antes (o al mismo tiempo) de empezar

- **Dado** que un administrador crea o edita un evento,
- **Cuando** envía `fecha_fin` menor o igual a `fecha_inicio` (sin importar si son del mismo día
  o de días distintos),
- **Entonces** el backend responde `400` con el mensaje "La fecha/hora de fin debe ser posterior
  a la fecha/hora de inicio", sin crear ni modificar el evento.

> Nota: como `fecha_inicio`/`fecha_fin` ya son `datetime` completos (fecha + hora), una sola
> comparación `fecha_fin > fecha_inicio` cubre tanto "evento de varios días" como "mismo día,
> hora de fin estrictamente mayor" — no son dos reglas distintas a implementar, es la misma
> regla aplicada a un valor que ya incluye la hora.

#### Criterio 2.2 — Selección de horas con time picker restringido dinámicamente

- **Dado** que un administrador está eligiendo la hora de fin de un evento que inicia y termina
  el mismo día calendario,
- **Cuando** abre el selector de hora de fin,
- **Entonces** las horas (y minutos de esa hora límite) menores o iguales a la hora de inicio
  aparecen deshabilitadas/no seleccionables en el propio selector, en vez de solo mostrar un
  mensaje de error después de elegir (ver especificación técnica §2.5 para el componente
  propuesto).
- **Dado** el mismo escenario en el modal de cronograma (horario de una actividad acotado al
  rango del evento),
- **Cuando** el usuario abre el selector de hora,
- **Entonces** las horas fuera del rango `[evento.fecha_inicio, evento.fecha_fin]` también
  aparecen deshabilitadas, no solo restringidas por `min`/`max` del input nativo.

### 3. Límite de caracteres end-to-end

#### Criterio 3.1 — Contador visual y bloqueo de escritura en el frontend

- **Dado** que un usuario escribe en un campo de texto limitado (p. ej. título de evento, máx.
  150 caracteres — ver tabla completa en §2.3 de la especificación técnica),
- **Cuando** alcanza el límite,
- **Entonces** el input no permite seguir escribiendo (`maxLength`) y se muestra un contador
  (p. ej. `128/150 caracteres`) que cambia de color (ámbar cerca del límite, rojo al llegar a
  él).

#### Criterio 3.2 — Rechazo en backend y en base de datos

- **Dado** que se envía un campo de texto que excede su límite definido (p. ej. desde un cliente
  distinto al frontend oficial, o un `curl` directo),
- **Cuando** la petición llega a la API,
- **Entonces** el esquema Pydantic la rechaza con `422` antes de tocar la base de datos.
- **Y**, como defensa en profundidad, la columna en base de datos (`VARCHAR(n)` o `TEXT` con
  `CHECK` de longitud) rechaza el `INSERT`/`UPDATE` con un error de integridad si ese límite se
  saltara por cualquier otra vía (script manual, otra integración, etc.).

### 4. Ubicación del evento con mapa interactivo

#### Criterio 4.1 — Registro de nombre del lugar + ubicación geográfica

- **Dado** que un administrador crea o edita un evento,
- **Cuando** llena el formulario,
- **Entonces** puede indicar tanto el **nombre del lugar** (campo `lugar`, ya existente) como,
  opcionalmente, su **ubicación geográfica** (dirección en texto y/o coordenadas), fijando el
  punto con un clic sobre un mapa interactivo embebido en el propio formulario.

#### Criterio 4.2 — Visualización del mapa en tarjeta/detalle

- **Dado** un evento con coordenadas registradas,
- **Cuando** un usuario abre su detalle,
- **Entonces** se muestra un mapa de solo lectura con un marcador en esa ubicación exacta.
- **Dado** un evento sin coordenadas (solo `lugar` como texto),
- **Cuando** se visualiza su tarjeta o detalle,
- **Entonces** no se muestra un mapa roto ni un marcador en `(0,0)`: el mapa se omite por
  completo y solo se ve el texto del lugar.

### 5. Navegación unificada

#### Criterio 5.1 — Un solo punto de entrada para Eventos + Cronograma

- **Dado** que la gestión de cronogramas ya es accesible desde la tarjeta y el detalle de cada
  evento (modal "Añadir cronograma", ya implementado),
- **Cuando** un usuario mira el menú de navegación superior,
- **Entonces** ya no existe un enlace de nivel superior "Cronogramas" separado de "Eventos" en
  el `Navbar` (hoy están duplicados: `src/components/layout/Navbar.tsx` tiene ambos) — la
  entrada a cronogramas ocurre siempre en el contexto de un evento específico.

> Nota de alcance: esto no implica borrar las rutas `/schedules/*` de administración standalone
> (pueden quedar vivas como vista avanzada), solo retirar el enlace del menú principal para no
> ofrecer dos caminos distintos a la misma función.

### 6. Responsive design

#### Criterio 6.1 — Los componentes nuevos se adaptan a móvil/tablet/escritorio

- **Dado** cualquiera de los componentes nuevos de este documento (time picker restringido,
  contador de caracteres, mapa interactivo),
- **Cuando** se visualizan en una pantalla de ancho móvil (< 640px),
- **Entonces** no se produce scroll horizontal de página, el texto no se solapa, y los controles
  táctiles (time picker, mapa) permanecen usables con el dedo (áreas de toque ≈ 40×40px o más).

---

## Parte 2 — Especificación técnica (Backend + Base de datos)

### 2.1 Principio general: dónde vive cada validación

Para mantener consistencia con lo ya implementado (`ScheduleService` ya sigue este patrón para
`hora_fin > hora_inicio`, rango y solape):

- **Esquema Pydantic (`422`)**: todo lo que se puede validar mirando *solo* el payload entrante
  — campo requerido, longitud mínima/máxima, tipo, rango numérico simple (p. ej. `capacidad >
  0`, `latitud` entre -90 y 90).
- **Capa de servicio (`400`, excepciones de dominio)**: todo lo que requiere el estado ya
  persistido o combinar varios campos entre sí — orden de fechas (`fecha_fin > fecha_inicio`),
  rango de un cronograma contra su evento, solapes contra otras filas en base de datos,
  existencia de la entidad referenciada.
- **Base de datos (`IntegrityError`, última línea de defensa)**: tipos de columna acotados
  (`VARCHAR(n)`) y `CHECK` constraints, para que un dato inválido no pueda persistir aunque la
  capa de aplicación tuviera un bug o se use otro cliente distinto a la API oficial.

El frontend (botón deshabilitado, `maxLength`, time picker restringido) es **solo UX** — nunca
el límite real de seguridad. Esa es la idea detrás del criterio 1.2.

### 2.2 `EventService` — nueva validación de rango de fechas

Hoy `EventService.create`/`update` (`src/application/events/services.py`) no valida el orden de
`fecha_inicio`/`fecha_fin` en absoluto. Propuesta, mismo patrón que `ScheduleService`:

```python
class InvalidEventDateRangeError(Exception):
    pass

# en create() y en update(), después de construir/mergear el EventModel:
if event.fecha_fin <= event.fecha_inicio:
    raise InvalidEventDateRangeError(
        "La fecha/hora de fin debe ser posterior a la fecha/hora de inicio"
    )
```

`src/api/v1/events/router.py`: capturar `InvalidEventDateRangeError` en `create_event` y
`update_event` → `HTTPException(400, ...)`, igual que ya se hace con los errores de
`ScheduleService`.

### 2.3 Límites de caracteres — tabla propuesta

| Tabla | Columna | Límite propuesto | Tipo de columna | Esquema Pydantic |
|---|---|---|---|---|
| `event` | `titulo` | 150 | `VARCHAR(150)` | `Field(min_length=1, max_length=150)` |
| `event` | `descripcion` | 2000 | `TEXT` + `CHECK (char_length(descripcion) <= 2000)` | `Field(min_length=1, max_length=2000)` |
| `event` | `lugar` | 200 | `VARCHAR(200)` | `Field(min_length=1, max_length=200)` |
| `event` | `direccion` *(nueva)* | 255 | `VARCHAR(255)` NULL | `Field(default=None, max_length=255)` |
| `cronogramas` | `actividad` | 150 | `VARCHAR(150)` | `Field(min_length=1, max_length=150)` |
| `cronogramas` | `descripcion` | 1000 | `TEXT` + `CHECK (char_length(descripcion) <= 1000)` | `Field(default=None, max_length=1000)` |
| `cronogramas` | `responsable` | 150 | `VARCHAR(150)` | `Field(min_length=1, max_length=150)` |

Migración Alembic (encadenada tras `a1b2c3d4e5f6`):
- `op.alter_column("event", "titulo", type_=sa.String(length=150))` (y análogos para `lugar`,
  `actividad`, `responsable`).
- `op.create_check_constraint("ck_event_descripcion_length", "event", "char_length(descripcion) <= 2000")`
  (y análogo para `cronogramas.descripcion`).
- **Pre-vuelo obligatorio antes de aplicar**: correr un `SELECT` que confirme que ninguna fila
  existente excede ya el nuevo límite (`SELECT id FROM event WHERE char_length(titulo) > 150`);
  si algo lo excede, decidir con el equipo si se trunca o se excluye de la migración ese campo.

Frontend: nuevo componente reutilizable `CharacterCounter` (o extender `TextField`/`TextArea`
para aceptar `maxLength` + mostrar el contador integrado), usado en `EventForm`, `ScheduleForm`
y `AddScheduleModal`.

### 2.4 Ubicación geográfica — nuevas columnas en `event`

```python
direccion: Mapped[str | None] = mapped_column(String(255), nullable=True)
latitud: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
longitud: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
```

Pydantic (`EventCreate`/`EventUpdate`/`EventResponse`):

```python
direccion: str | None = Field(default=None, max_length=255)
latitud: float | None = Field(default=None, ge=-90, le=90)
longitud: float | None = Field(default=None, ge=-180, le=180)
```

Las tres son opcionales: un evento puede seguir existiendo solo con `lugar` como texto libre
(criterio 4.2). Regla de negocio mínima a nivel de servicio: si se envía `latitud`, debe venir
`longitud` también (y viceversa) — par completo o ninguno; si no, `400`.

**Librería de mapa recomendada: Leaflet + OpenStreetMap** (no Google Maps/Mapbox): no requiere
API key ni facturación, es la opción de menor costo/riesgo operativo para un proyecto que hoy no
tiene ninguna credencial de mapas configurada, y se integra bien sin depender de un SDK pesado.
Frontend: un componente `EventLocationMap` (mapa de solo lectura con marcador) para
tarjeta/detalle, y un modo editable (clic para fijar el pin) dentro de `EventForm`.

### 2.5 Time picker restringido — propuesta de componente

En vez de adoptar una librería nueva, extender el patrón ya existente
(`src/pages/schedules/components/TimeSelect.tsx`, selects de hora/minuto/AM-PM) para aceptar un
rango permitido opcional (`minTime`/`maxTime` en `HH:mm`) y deshabilitar (`disabled` en el
`<option>`) las horas/minutos fuera de ese rango, en vez de solo validar después de elegir. Esto
mantiene la convención ya establecida del proyecto (sin date-picker de terceros) y se reutiliza
tanto en `EventForm` (hora de fin acotada por hora de inicio, mismo día) como en
`AddScheduleModal` (actividad acotada al rango del evento).

### 2.6 Navbar — quitar el enlace duplicado

Cambio puramente de frontend: eliminar el `<NavLink to="/schedules">` de
`src/components/layout/Navbar.tsx` (líneas ~59-61 a la fecha de este documento). Las rutas
`/schedules/*` siguen existiendo en `router.tsx` para quien llegue por URL directa o por el
enlace "Ver en Cronogramas" del detalle de evento; solo se retira del menú principal.
