# Mudar de Colombia S.A.S. — Contexto del Proyecto

## Descripción General
Aplicación web para la gestión de DOMs (Documentos Origen Mudar) que rastrea el ciclo de vida completo de producción: planeación, producción, tratamiento térmico, despachos y entregas.

## Stack Tecnológico

- **Backend:** Django REST Framework + PostgreSQL
- **Frontend:** React + Vite (en construcción)
- **Autenticación:** Token Authentication (`rest_framework.authtoken`) — DRF nativo, no simplejwt

## Arquitectura del Backend

### Estructura de Módulos
El backend está organizado en módulos. Cada módulo sigue este patrón:

```
models.py → serializers.py → views.py → urls.py
```

### Módulos

| # | Módulo | Estado |
|---|---|---|
| 1 | Listas Predefinidas | Validado |
| 2 | Gestión de DOMs | Validado |
| 3 | Registro de Producción | Validado |
| 4 | Registro de Planeación | Validado |
| 5 | Cronómetro | Validado |
| 6 | Dashboard / Reportes | Validado |

## Convenciones Establecidas

### Modelos

- Todos los nombres de campo en `snake_case`
- Todo modelo tiene `verbose_name` y `ordering` en la clase `Meta`
- `numero_registro` es siempre auto-generado — nunca escribible vía API
- `dom` FK es siempre asignado del lado del servidor — nunca escribible vía API
- Los métodos `save()` personalizados no deben referenciar campos inexistentes

### Serializers

- Todos los campos del modelo deben estar listados explícitamente en `fields`
- `read_only_fields` debe incluir siempre: `numero_registro`, `dom`
- Los serializers anidados deben coincidir exactamente con la estructura del modelo relacionado
- Las propiedades calculadas (`tiempo_proyectado`, `cantidad_pendiente`, `sumatoria_tiempo_asignado_turnos`, `tiempo_restante_dia`) dependen de que `fecha_planeacion` y `cantidad_pedido` estén presentes en `fields`

### Vistas

- `select_related` debe cubrir todas las FK usadas en el serializer
- `serializer.save()` debe pasar todos los argumentos FK requeridos explícitamente (ej. `dom=dom`, `productoDom=dom`)
- Se requiere un refresh con `select_related` antes del `return Response` cuando se retornan propiedades calculadas
- Todas las vistas deben definir `permission_classes`

## Características Importantes

### 1. Patrón de bloqueo de etapas
Cada etapa tiene un campo boolean de bloqueo. Una vez marcado `True`, la etapa no puede modificarse vía API:

| Etapa | Modelo | Campo de bloqueo |
|---|---|---|
| 2 — Planeación | `RegistroPlaneacion` | `planeacion_completa` |
| 3 — Almacén | `RegistroAlmacen` | `materias_liberadas` |
| 4 — Producción | `RegistroProduccion` | `cierre_produccion` |
| 5 — Tratamiento | `RegistroTratamiento` | `tratamiento_completado` |
| 6 — Despacho | `Dom` | `dom_liberado_cierre` |

**Bloqueo desactivado deliberadamente — etapa 1 (Gestión comercial y diseño):** el modelo `Dom` tiene el campo `dom_relacionado_produccion` y el método `etapa_1_bloqueada()` (`models.py:256,319-320`), pero desde 2026-07-02 el bloqueo de esta etapa está **desactivado a propósito** — se quitó `'etapa_1': dom.etapa_1_bloqueada` del diccionario `bloqueos` en `DomDetalleView.put` (`views.py`) para evitar que un usuario bloquee la etapa por error, y se retiró el campo `CampoFormulario` "Validación etapa 1" del frontend (`PaginaEditarDom.jsx`) para que no sea visible ni editable. El campo del modelo, el método y el serializer siguen intactos — es código muerto reversible. Si el dueño del negocio pide reactivar este bloqueo en el futuro, hay que: (1) volver a agregar `'etapa_1': dom.etapa_1_bloqueada,` al diccionario `bloqueos`, y (2) restaurar el `CampoFormulario` correspondiente en el frontend.

### 2. Modelo `RegistroTurnoDia` (migración 0005)
Registra operarios disponibles por turno y fecha. Es la base del cálculo de `capacidad_turno_dia` en `RegistroPlaneacion`. Sus campos clave: `turno` (FK), `fecha`, `numero_operarios`, `horas_extras` (+120 min si `True`). Restricción: `unique_together = ('turno', 'fecha')`.

### 3. Propiedades calculadas en `RegistroPlaneacion`
Las siguientes propiedades se calculan en tiempo de ejecución y **no se almacenan en BD**. Requieren `select_related` y refresh antes del `Response`:
- `capacidad_turno_dia` — minutos totales disponibles del turno × operarios (+ extras si aplica)
- `tiempo_proyectado` — `cantidad_pedido × tiempo_produccion_unitario`
- `sumatoria_tiempo_asignado_turnos` — suma de tiempos proyectados de todos los registros del mismo turno y fecha
- `tiempo_restante_dia` — `capacidad_turno_dia - sumatoria_tiempo_asignado_turnos`

### 4. Sistema de roles (`PerfilUsuario`)
Define 6 roles con permisos diferenciados por etapa via `puede_editar_etapas(etapa)`:

| Rol | Etapas permitidas |
|---|---|
| `ADMIN` | 0, 1, 2, 3, 4, 5, 6 |
| `ANALISTA_1` / `ANALISTA_2` | 0, 1, 6 |
| `PLANEADOR` | 2 |
| `LIDER_PLANTA` | 3, 4, 5 |
| `GERENCIA` | ninguna (solo lectura) |

### 5. Limitación conocida — cronómetro y cambio de operarios
`minutos_hombre_produccion_dom = minutos_asignados × numero_personas_asignadas` asume un único valor de personas para toda la duración. Si el número de operarios cambia a mitad del cronómetro, el cálculo aplica el valor final retroactivamente y el resultado es incorrecto. Flujo soportado: `numero_personas_asignadas` se confirma antes de iniciar y no cambia durante la producción. Cambio mid-cronómetro no está implementado ni soportado — requeriría registrar segmentos de tiempo.

### 6. Gestión de secretos y entorno
- Las credenciales de BD y `SECRET_KEY` se leen desde `.env` via `python-decouple` (`config()`)
- `.env` está excluido del repositorio — nunca debe commitearse
- El `.gitignore` cubre: `.env`, `*.sqlite3`, `__pycache__/`, `*.pyc`, `venv/`, `node_modules`

## Pendientes

- **Validar visibilidad de campos `SelectSiNo` sin permisos de edición** — `client/src/components/common/SelectSiNo.jsx` tiene dos variantes activas en paralelo, falta validar en navegador y decidir cuál queda:
  - Etapa 2 (Planeación, 11 campos): prop `mostrarCandado` activa — radio seleccionado se mantiene azul fijo, señal de bloqueo es un ícono de candado (`FiLock`) junto a los radios.
  - Resto de etapas (Almacén, Producción, Tratamiento, Despacho, DOM): sin candado — radio azul cuando editable, negro sólido cuando bloqueado.
  - Pendiente decidir si se extiende el candado a todas las etapas o se queda solo en Planeación.
- **Contraste de campos deshabilitados aún no convence al usuario** — se aplicaron varias capas de fix (contraste de texto/fondo en `disabled:*`, override global de `-webkit-text-fill-color`/`opacity` en `client/src/index.css`), pero tras probarlo en navegador el usuario indicó que el aspecto visual sigue sin convencerlo. Retomar y revisar con el usuario antes de seguir iterando a ciegas.

## Deuda técnica / mejoras a futuro

- **Cronómetro — cambio de operarios a mitad de la producción** — la fórmula `minutos_hombre_produccion_dom = minutos_asignados × numero_personas_asignadas` asume un único valor de personas para toda la duración (ver sección 5, "Limitación conocida"). Si el número de operarios cambia mid-cronómetro, el cálculo aplica el valor final retroactivamente y el resultado es incorrecto. Mejora potencial: registrar segmentos de tiempo con su respectivo `numero_personas_asignadas` y sumar `minutos_hombre` por segmento, en lugar de un único producto global. No priorizado — el flujo actual (confirmar personas antes de iniciar y no cambiarlas durante la producción) es suficiente para el negocio hoy.

## Resumen de Sesión — 2026-05-14

### Auditoría y correcciones aplicadas

| # | Categoría | Acción |
|---|---|---|
| 1 | Seguridad | `.gitignore` ampliado: añadidas entradas para `.env`, `*.sqlite3`, `__pycache__/`, `*.pyc`, `venv/`, `.venv/` |
| 2 | Seguridad | `SECRET_KEY` en `settings.py` reemplazado por `config('SECRET_KEY')` — ya no está hardcodeado |
| 3 | Limpieza git | `db.sqlite3` removido del índice (residuo del proyecto académico; BD migrada a PostgreSQL) |
| 4 | Limpieza git | 17 archivos `.pyc` y carpetas `__pycache__` removidos del repositorio, incluyendo bytecode huérfano `test_unidad.cpython-310.pyc` |
| 5 | Dependencias | `requirements.txt` actualizado con `python-decouple==3.8` y `psycopg2-binary==2.9.11` |
| 6 | Admin | `RegistroTurnoDia` registrado en `admin.py` (omitido al crear el modelo en migración 0005) |
| 7 | Migraciones | `0005_registroturnodia.py` añadido al repositorio (existía localmente pero nunca fue commiteado) |
| 8 | Documentación | `CLAUDE.md` corregido: autenticación (`simplejwt` → `rest_framework.authtoken`), formato mejorado, características clave añadidas |
