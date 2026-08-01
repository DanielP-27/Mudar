# Mudar de Colombia S.A.S. — Contexto del Proyecto

## 1. Descripción General
Aplicación web para la gestión de DOMs (Documentos Origen Mudar) que rastrea el ciclo de vida completo de producción: planeación, producción, tratamiento térmico, despachos y entregas.

## 2. Stack Tecnológico

- **Backend:** Django REST Framework + PostgreSQL
- **Frontend:** React + Vite (en construcción)
- **Autenticación:** Token Authentication (`rest_framework.authtoken`) — DRF nativo, no simplejwt

## 3. Arquitectura del Backend

### 3.1 Estructura de módulos
El backend está organizado en módulos. Cada módulo sigue este patrón:

```
models.py → serializers.py → views.py → urls.py
```

### 3.2 Estado de los módulos

| # | Módulo | Estado |
|---|---|---|
| 1 | Listas Predefinidas | Validado |
| 2 | Gestión de DOMs | Validado |
| 3 | Registro de Producción | Validado |
| 4 | Registro de Planeación | Validado |
| 5 | Cronómetro | Validado |
| 6 | Dashboard / Reportes | Validado |

## 4. Convenciones de Código

### 4.1 Modelos

- Todos los nombres de campo en `snake_case`
- Todo modelo tiene `verbose_name` y `ordering` en la clase `Meta`
- `numero_registro` es siempre auto-generado — nunca escribible vía API
- `dom` FK es siempre asignado del lado del servidor — nunca escribible vía API
- Los métodos `save()` personalizados no deben referenciar campos inexistentes

### 4.2 Serializers

- Todos los campos del modelo deben estar listados explícitamente en `fields`
- `read_only_fields` debe incluir siempre: `numero_registro`, `dom`
- Los serializers anidados deben coincidir exactamente con la estructura del modelo relacionado
- Las propiedades calculadas (`tiempo_proyectado`, `cantidad_pendiente`, `sumatoria_tiempo_asignado_turnos`, `tiempo_restante_dia`) dependen de que `fecha_planeacion` y `cantidad_pedido` estén presentes en `fields`

### 4.3 Vistas

- `select_related` debe cubrir todas las FK usadas en el serializer
- `serializer.save()` debe pasar todos los argumentos FK requeridos explícitamente (ej. `dom=dom`, `productoDom=dom`)
- Se requiere un refresh con `select_related` antes del `return Response` cuando se retornan propiedades calculadas
- Todas las vistas deben definir `permission_classes`

## 5. Reglas de Negocio y Características Clave

### 5.1 Patrón de bloqueo de etapas
Cada etapa tiene un campo boolean de bloqueo. Una vez marcado `True`, la etapa no puede modificarse vía API:

| Etapa | Modelo | Campo de bloqueo |
|---|---|---|
| 2 — Planeación | `RegistroPlaneacion` | `planeacion_completa` |
| 3 — Almacén | `RegistroAlmacen` | `materias_liberadas` |
| 4 — Producción | `RegistroProduccion` | `cierre_produccion` |
| 5 — Tratamiento | `RegistroTratamiento` | `tratamiento_completado` |
| 6 — Despacho | `Dom` | `dom_liberado_cierre` |

**Etapa 1 (Gestión comercial y diseño) — bloqueo ACTIVO.** Se bloquea con `dom_relacionado_produccion=True`. Estuvo desactivado entre el 2026-07-02 y el 2026-07-06, y fue **reactivado el 2026-07-06**, cableado por el modal de confirmación del frontend. Hoy `'etapa_1': dom.etapa_1_bloqueada` está en el diccionario `bloqueos` de `DomDetalleView.put` (`views.py:1788`), junto a `'etapa_6'`.
> *(Corregido el 2026-07-31, verificado contra código: esta sección afirmaba lo contrario.)*

> **Nota:** ningún check de bloqueo exceptúa al rol `ADMIN` — un registro bloqueado queda bloqueado también para el administrador. El desbloqueo **no** se resolvió con una excepción de rol sino con un **endpoint dedicado**: `POST /api/desbloqueo/` → `DesbloqueoEtapaView` (`views.py:1859`), restringido a ADMIN, idempotente (si ya estaba abierto responde 200 sin escribir) y con registro en `AuditoriaDom` como `DESBLOQUEO_ETAPA`. El mapa etapa→modelo→campo vive en `MAPA_DESBLOQUEO` (`views.py:1854`). En el frontend, el botón **Reabrir** de `PaginaListaDoms.jsx:499` (tabla) y `:579` (tarjeta móvil) lo consume para la etapa 6.

> **Salvaguarda de cierre (2026-08-01).** Una etapa **no puede bloquearse si su campo de veredicto sigue sin diligenciar**. El valor puede ser verdadero o falso según la realidad del negocio; lo que no se admite es el nulo, porque el DOM quedaría cerrado para todos y el dato que alimenta los informes nunca habría existido. Vive en `views.py`: `valor_efectivo` resuelve el valor que tendrá el campo **después** de aplicar el payload —veredicto y candado viajan en el mismo PUT—, `REQUISITOS_CIERRE` declara los requisitos por etapa y `validar_cierre` devuelve el mensaje o `None`.
>
> | Etapa | Candado | Exige |
> |---|---|---|
> | 3 — Almacén | `materias_liberadas` | `dom_realizado_planeacion` |
> | 4 — Producción | `cierre_produccion` | `segun_planeacion`, `numero_personas_asignadas` y cronómetro finalizado |
> | 5 — Tratamiento | `tratamiento_completado` | `tratamiento_segun_planeacion` |
> | 6 — Despacho | `dom_liberado_cierre` | `dom_entregado_ok` |
>
> ⚠️ **La etapa 4 está declarada en `REQUISITOS_CIERRE` pero NO cableada.** `RegistroProduccionDetalleView.put` conserva su bloque propio, que solo exige el cronómetro. Se dejó así a propósito: es la única de las cuatro que sustituye código en funcionamiento. Al cablearla se ganan dos requisitos que hoy no se exigen. La etapa 2 no tiene campo de veredicto; su guarda —turno, fecha, operarios, duración y al menos un producto con cantidad— queda para el bloque de endurecimiento previo al piloto.

### 5.2 Sistema de roles (`PerfilUsuario`)
Define 6 roles con permisos diferenciados por etapa via `puede_editar_etapas(etapa)`:

| Rol | Etapas permitidas |
|---|---|
| `ADMIN` | 0, 1, 2, 3, 4, 5, 6 |
| `ANALISTA_1` / `ANALISTA_2` | 0, 1, 6 |
| `PLANEADOR` | 2 |
| `LIDER_PLANTA` | 3, 4, 5 |
| `GERENCIA` | ninguna (solo lectura) |

### 5.3 Capacidad de turno — `RegistroTurnoDia` (migración 0005)
Registra operarios disponibles por turno y fecha. Es la base del cálculo de `capacidad_turno_dia` en `RegistroPlaneacion`. Sus campos concretos son: `turno` (FK), `fecha`, `numero_operarios`, `minutos_totales`, `registrado_por` y `fecha_creacion`. Restricción: `unique_together = ('turno', 'fecha')`.
> *(Corregido el 2026-07-31, verificado contra código: esta sección citaba un campo `horas_extras` (+120 min si `True`) que no existe en el modelo. La duración del turno se guarda en `minutos_totales`.)*

### 5.4 Propiedades calculadas en `RegistroPlaneacion`
Las siguientes propiedades se calculan en tiempo de ejecución y **no se almacenan en BD**. Requieren `select_related` y refresh antes del `Response`:
- `capacidad_turno_dia` — minutos del turno × operarios del turno-día. El resultado son **minutos-persona**, que es la unidad en la que el sistema mide toda la carga de trabajo. Esa unidad **no está declarada en ningún `verbose_name` ni comentario**: se deduce de que `tiempo_restante_dia` le resta el tiempo proyectado, y de que `tiempo_produccion_unitario` es el promedio de minutos que **una persona** tarda en una unidad, obtenido de año y medio de registros en papel. *(Corregido el 2026-08-01: esta línea decía "(+ extras si aplica)", residuo de una constante muerta — ver 8.3.4.)*
- `tiempo_proyectado` — `cantidad_pedido × tiempo_produccion_unitario`
- `sumatoria_tiempo_asignado_turnos` — suma de tiempos proyectados de todos los registros del mismo turno y fecha
- `tiempo_restante_dia` — `capacidad_turno_dia - sumatoria_tiempo_asignado_turnos`

### 5.5 Cronómetro — limitación conocida (cambio de operarios)
`minutos_hombre_produccion_dom = minutos_asignados × numero_personas_asignadas` asume un único valor de personas para toda la duración. Si el número de operarios cambia a mitad del cronómetro, el cálculo aplica el valor final retroactivamente y el resultado es incorrecto. Flujo soportado: `numero_personas_asignadas` se confirma antes de iniciar y no cambia durante la producción. Cambio mid-cronómetro no está implementado ni soportado — requeriría registrar segmentos de tiempo (ver deuda 8.1.1).

## 6. Seguridad y Entorno

- Las credenciales de BD y `SECRET_KEY` se leen desde `.env` via `python-decouple` (`config()`)
- `.env` está excluido del repositorio — nunca debe commitearse
- El `.gitignore` cubre: `node_modules`, `venv/`, `.venv/`, `.env` **y `.env.*` con excepción explícita `!.env.example`**, `__pycache__/`, `*.pyc`, `*.pyo`, `client/dist`, `client/node_modules`, `staticfiles/`, `*.log`, `logs/`, `.vscode/`, `.idea/`. Ya **no** incluye `*.sqlite3` — se retiró por política de clean code, la base es PostgreSQL y el archivo se borró del disco

## 7. Pendientes (previos al entorno de pruebas)

### 7.1 Visibilidad de campos `SelectSiNo` sin permisos de edición — ✅ RESUELTO
La prop `mostrarCandado` y el ícono `FiLock` **ya no existen** en el componente. `SelectSiNo` recibe hoy `variante = 'bloqueo' | 'lectura'` y, cuando el usuario no puede editar la etapa (`soloLectura`), pinta una **píldora legible** en vez de radios deshabilitados —que el navegador agrisaba hasta hacerlos ilegibles—: ámbar **reservada a los campos de bloqueo de etapa**, gris estándar para el resto, y `—` cuando aún no se ha diligenciado.
> *(Corregido el 2026-07-31, verificado contra código: esta sección describía dos variantes en paralelo que ya no están.)*

### 7.2 Contraste de campos deshabilitados
Se aplicaron varias capas de fix (contraste de texto/fondo en `disabled:*`, override global de `-webkit-text-fill-color`/`opacity` en `client/src/index.css`), pero tras probarlo en navegador el usuario indicó que el aspecto visual sigue sin convencerlo. Retomar y revisar con el usuario antes de seguir iterando a ciegas.

### 7.3 Desbloqueo por ADMIN de etapas bloqueadas — ✅ RESUELTO
Se implementó la opción preferida: **endpoint dedicado con auditoría**, no excepción de rol. `POST /api/desbloqueo/` (`urls.py:108`) → `DesbloqueoEtapaView` (`views.py:1859`) recibe `tipo` y `registro_id`, valida rol ADMIN, baja el candado con `save(update_fields=[campo])` y registra `DESBLOQUEO_ETAPA` en `AuditoriaDom` con el antes/después. Los checks de bloqueo de las etapas siguen **sin** excepción de rol, que es lo correcto: el desbloqueo es un acto explícito y trazable, no un permiso silencioso. Detalle en la nota de la sección 5.1.
> *(Corregido el 2026-07-31, verificado contra código: figuraba como funcionalidad faltante con la decisión abierta.)*

## 8. Deuda Técnica / Mejoras a Futuro (post-pruebas)

> Ítems diferidos deliberadamente para DESPUÉS del entorno de pruebas.
> Ninguno bloquea el despliegue de pruebas; se listan para no perder trazabilidad.

### 8.1 Cronómetro

**8.1.1 Cambio de operarios a mitad de la producción** — la fórmula `minutos_hombre_produccion_dom = minutos_asignados × numero_personas_asignadas` asume un único valor de personas para toda la duración (ver 5.5). Mejora potencial: registrar segmentos de tiempo con su respectivo `numero_personas_asignadas` y sumar `minutos_hombre` por segmento, en lugar de un único producto global. No priorizado — el flujo actual (confirmar personas antes de iniciar y no cambiarlas durante la producción) es suficiente para el negocio hoy.

Relacionado (pendiente post-pruebas, 2026-07-12): analizar y establecer un mecanismo que **permita modificar `numero_personas_asignadas` (incluso mid-turno) recalculando correctamente** las métricas derivadas (`minutos_hombre_produccion_dom`, `minutos_restantes_dom`, `cumplimiento_produccion`). Como guardarraíl temporal, el frontend bloquea el campo una vez confirmado en el modal (P6), justamente porque hoy no existe ese recálculo.

**8.1.2 Auditoría de eventos y usuario que finaliza** — `RegistroTiempoProduccion` tiene un único campo `usuario` que se escribe solo al INICIAR (`CronometroIniciarView`). Al finalizar (`CronometroFinalizarView`) no se registra quién finalizó, y las vistas del cronómetro (Iniciar/Pausar/Reanudar/Finalizar) no llaman a `registrar_auditoria`. Por lo tanto, si un LIDER_PLANTA inicia y otro finaliza, el segundo no queda registrado en ningún lado. Enfoque acordado (opción 3): registrar auditoría por cada evento de cronómetro. Diferido post-pruebas y condicionado a la decisión del control de crono por usuario creador. Se implementará junto con 8.1.3.

**8.1.3 Cierre automático / alerta de cronómetros olvidados** — un cronómetro puede quedar EN_CURSO indefinidamente (ej. olvidar finalizarlo → contabiliza 40 h). Corrompe `minutos_totales`. Pendiente definir política (auto-cierre por tope, alerta, o ambos). Se construirá junto con el panel de cronómetros activos del dashboard (funcionalidad solicitada por el cliente en el demo del 2026-07-10).

### 8.2 Datos

**8.2.1 Tolerancia del `<select>` de duración de turno a valores fuera de `choices`** — `PaginaEditarDom.jsx:361` carga el valor guardado en un `<select>` cuyas opciones son solo las vigentes (`OPCIONES_MINUTOS`, `:39-42`). Si el registro trae una duración de una legislación anterior, ninguna opción coincide y **el campo se muestra vacío**. No afecta a producción hoy (la base arranca vacía y todo lo escrito tras la 0019 es válido), pero **el próximo cambio de legislación reproduce la situación con datos reales**. Arreglo: inyectar el valor actual como opción adicional. ~20-30 min, va al bloque de endurecimiento previo al piloto.

> ✅ **CERRADO el 2026-08-01 — la migración retroactiva de turnos 480/600 → 420/540 NO se hace, y no era deuda técnica.** Los 480/600 son el registro fiel de jornadas que de verdad duraban 8 y 10 horas antes del cambio de legislación. Verificado: las **29** filas fuera de `choices` se crearon **todas antes** de la migración 0019, y las **5** posteriores están las 5 en 420/540 — el camino de escritura no ha admitido un solo valor inválido. Además, en producción la base arranca vacía.
>
> ⛔ **Retractada la advertencia del 2026-07-31** que decía que el catálogo `Turno` alimentaba la validación de capacidad: **es falsa**. La capacidad sale siempre de `RegistroTurnoDia` — `capacidad_turno_dia` (`models.py:414`) y `preview_capacidad` (`models.py:175`). Grep de `turno.minutos_totales` en todo el proyecto: cero coincidencias. `Turno.minutos_totales` (480 en pk 1 y 3) es dato muerto que solo aparece en su `__str__`; queda pendiente decidir si se corrige o se elimina el campo.

### 8.3 Refactors

**8.3.1 PUT atómico planeación + cantidades (Opción A)** — hoy la planeación y sus cantidades se guardan en dos pasos separados. Se decidió unificarlos en un único PUT atómico, pero DIFERIDO para después de pruebas; los endpoints actuales se mantienen intactos para no romper el flujo de pruebas.

**8.3.2 Wrapper `CampoSiNo`** — componente envoltorio que centralice permiso por etapa + variante + estado de bloqueo, en vez de repetir `soloLectura`/`disabled` en ~25 campos de `PaginaEditarDom.jsx`. Post-pruebas.

**8.3.3 Centralizar el sistema de toasts** — hoy `Toast.jsx` es solo presentacional (éxito, controlado); cada página replica su propio estado `exito` + helper `mostrarExito` con el `setTimeout` de duración (3 copias: `PaginaEditarDom`, `PaginaClientes`, `PaginaProductos`). Además no hay toast de error (los errores van por `ModalMensaje` o texto rojo inline, según la página). Mejora: un `useToast` (hook) o `ToastProvider` (context) que centralice estado + duración y soporte variantes éxito/error, para que cualquier página dispare `toast.exito(...)` / `toast.error(...)` desde una sola fuente de verdad. Post-pruebas.

**8.3.4 Código muerto que fabrica documentación falsa** — `MINUTOS_HORAS_EXTRAS = 120` (`models.py:9`) **no se usa en ninguna parte** y no existe ningún campo `horas_extras` en ningún modelo. Pero **dos comentarios describen ese comportamiento inexistente**: `models.py:8` y `models.py:121`. Esos comentarios son el **origen del error de la sección 5.3** — quien escribió la documentación leyó el comentario y le creyó, y de ahí pasó a razonamientos posteriores. Es una categoría distinta de las divergencias entre implementaciones: es divergencia **entre la descripción y el código**, y se propaga. Arreglo: borrar la constante y los dos comentarios.

**8.3.5 Revisión de comentarios y declaración de unidades** — barrido de los comentarios existentes en `models.py` y `views.py` para detectar los que describen comportamiento distinto del que implementan, y adición de comentarios donde falta contexto que hoy solo vive en la cabeza de quien lo escribió. Casos concretos ya detectados: el comentario de `minutos_hombre_produccion_dom` (`models.py:700`) describe `tiempo_proyectado`, no la propiedad que encabeza; el `help_text` de `tiempo_produccion_unitario` está **vacío** y debería decir que es el promedio de minutos que **una persona** tarda en una unidad, obtenido de año y medio de registros en papel; `capacidad_turno_dia` no declara que su resultado son minutos-persona (ver 5.4). **La regla:** cuando una propiedad devuelve una magnitud, el comentario debe decir **en qué unidad** y **de dónde sale el dato**. No es documentación por documentar — es que estas confusiones no producen ningún error visible y sobreviven meses.

## 9. Historial de Sesiones

### 9.1 Auditoría y correcciones — 2026-05-14

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
