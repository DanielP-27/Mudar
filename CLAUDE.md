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

**Bloqueo desactivado deliberadamente — etapa 1 (Gestión comercial y diseño):** el modelo `Dom` tiene el campo `dom_relacionado_produccion` y el método `etapa_1_bloqueada()` (`models.py:256,319-320`), pero desde 2026-07-02 el bloqueo de esta etapa está **desactivado a propósito** — se quitó `'etapa_1': dom.etapa_1_bloqueada` del diccionario `bloqueos` en `DomDetalleView.put` (`views.py`) para evitar que un usuario bloquee la etapa por error, y se retiró el campo `CampoFormulario` "Validación etapa 1" del frontend (`PaginaEditarDom.jsx`) para que no sea visible ni editable. El campo del modelo, el método y el serializer siguen intactos — es código muerto reversible. Si el dueño del negocio pide reactivar este bloqueo en el futuro, hay que: (1) volver a agregar `'etapa_1': dom.etapa_1_bloqueada,` al diccionario `bloqueos`, y (2) restaurar el `CampoFormulario` correspondiente en el frontend.

> **Nota:** ningún check de bloqueo exceptúa hoy al rol `ADMIN` — un registro bloqueado queda bloqueado también para el administrador. El desbloqueo por ADMIN es una funcionalidad faltante (pendiente pre-pruebas, ver sección 7).

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
Registra operarios disponibles por turno y fecha. Es la base del cálculo de `capacidad_turno_dia` en `RegistroPlaneacion`. Sus campos clave: `turno` (FK), `fecha`, `numero_operarios`, `horas_extras` (+120 min si `True`). Restricción: `unique_together = ('turno', 'fecha')`.

### 5.4 Propiedades calculadas en `RegistroPlaneacion`
Las siguientes propiedades se calculan en tiempo de ejecución y **no se almacenan en BD**. Requieren `select_related` y refresh antes del `Response`:
- `capacidad_turno_dia` — minutos totales disponibles del turno × operarios (+ extras si aplica)
- `tiempo_proyectado` — `cantidad_pedido × tiempo_produccion_unitario`
- `sumatoria_tiempo_asignado_turnos` — suma de tiempos proyectados de todos los registros del mismo turno y fecha
- `tiempo_restante_dia` — `capacidad_turno_dia - sumatoria_tiempo_asignado_turnos`

### 5.5 Cronómetro — limitación conocida (cambio de operarios)
`minutos_hombre_produccion_dom = minutos_asignados × numero_personas_asignadas` asume un único valor de personas para toda la duración. Si el número de operarios cambia a mitad del cronómetro, el cálculo aplica el valor final retroactivamente y el resultado es incorrecto. Flujo soportado: `numero_personas_asignadas` se confirma antes de iniciar y no cambia durante la producción. Cambio mid-cronómetro no está implementado ni soportado — requeriría registrar segmentos de tiempo (ver deuda 8.1.1).

## 6. Seguridad y Entorno

- Las credenciales de BD y `SECRET_KEY` se leen desde `.env` via `python-decouple` (`config()`)
- `.env` está excluido del repositorio — nunca debe commitearse
- El `.gitignore` cubre: `.env`, `*.sqlite3`, `__pycache__/`, `*.pyc`, `venv/`, `node_modules`

## 7. Pendientes (previos al entorno de pruebas)

### 7.1 Visibilidad de campos `SelectSiNo` sin permisos de edición
`client/src/components/common/SelectSiNo.jsx` tiene dos variantes activas en paralelo, falta validar en navegador y decidir cuál queda:
- Etapa 2 (Planeación, 11 campos): prop `mostrarCandado` activa — radio seleccionado se mantiene azul fijo, señal de bloqueo es un ícono de candado (`FiLock`) junto a los radios.
- Resto de etapas (Almacén, Producción, Tratamiento, Despacho, DOM): sin candado — radio azul cuando editable, negro sólido cuando bloqueado.
- Pendiente decidir si se extiende el candado a todas las etapas o se queda solo en Planeación.

### 7.2 Contraste de campos deshabilitados
Se aplicaron varias capas de fix (contraste de texto/fondo en `disabled:*`, override global de `-webkit-text-fill-color`/`opacity` en `client/src/index.css`), pero tras probarlo en navegador el usuario indicó que el aspecto visual sigue sin convencerlo. Retomar y revisar con el usuario antes de seguir iterando a ciegas.

### 7.3 Desbloqueo por ADMIN de etapas bloqueadas
Confirmado en `views.py`: ningún check de bloqueo (`etapa2_bloqueada()`, `etapa_3_bloqueada()`, etc., ni el dict `bloqueos` de etapas 1/6) exceptúa al rol `ADMIN`. Por diseño acordado con el cliente, el administrador debe poder desbloquear cualquier etapa de cualquier DOM. Funcionalidad faltante — resolver antes de pruebas. Decisión pendiente: excepción de rol en el check vs. endpoint dedicado de desbloqueo con auditoría (preferencia: endpoint dedicado, por trazabilidad).

## 8. Deuda Técnica / Mejoras a Futuro (post-pruebas)

> Ítems diferidos deliberadamente para DESPUÉS del entorno de pruebas.
> Ninguno bloquea el despliegue de pruebas; se listan para no perder trazabilidad.

### 8.1 Cronómetro

**8.1.1 Cambio de operarios a mitad de la producción** — la fórmula `minutos_hombre_produccion_dom = minutos_asignados × numero_personas_asignadas` asume un único valor de personas para toda la duración (ver 5.5). Mejora potencial: registrar segmentos de tiempo con su respectivo `numero_personas_asignadas` y sumar `minutos_hombre` por segmento, en lugar de un único producto global. No priorizado — el flujo actual (confirmar personas antes de iniciar y no cambiarlas durante la producción) es suficiente para el negocio hoy.

Relacionado (pendiente post-pruebas, 2026-07-12): analizar y establecer un mecanismo que **permita modificar `numero_personas_asignadas` (incluso mid-turno) recalculando correctamente** las métricas derivadas (`minutos_hombre_produccion_dom`, `minutos_restantes_dom`, `cumplimiento_produccion`). Como guardarraíl temporal, el frontend bloquea el campo una vez confirmado en el modal (P6), justamente porque hoy no existe ese recálculo.

**8.1.2 Auditoría de eventos y usuario que finaliza** — `RegistroTiempoProduccion` tiene un único campo `usuario` que se escribe solo al INICIAR (`CronometroIniciarView`). Al finalizar (`CronometroFinalizarView`) no se registra quién finalizó, y las vistas del cronómetro (Iniciar/Pausar/Reanudar/Finalizar) no llaman a `registrar_auditoria`. Por lo tanto, si un LIDER_PLANTA inicia y otro finaliza, el segundo no queda registrado en ningún lado. Enfoque acordado (opción 3): registrar auditoría por cada evento de cronómetro. Diferido post-pruebas y condicionado a la decisión del control de crono por usuario creador. Se implementará junto con 8.1.3.

**8.1.3 Cierre automático / alerta de cronómetros olvidados** — un cronómetro puede quedar EN_CURSO indefinidamente (ej. olvidar finalizarlo → contabiliza 40 h). Corrompe `minutos_totales`. Pendiente definir política (auto-cierre por tope, alerta, o ambos). Se construirá junto con el panel de cronómetros activos del dashboard (funcionalidad solicitada por el cliente en el demo del 2026-07-10).

### 8.2 Datos

**8.2.1 Migración de turnos históricos 480/600 → 420/540** — el cambio de legislación (migración 0019, 2026-07-10) ajustó la duración de los turnos, pero los registros `RegistroTurnoDia` creados antes conservan la duración anterior. Definir si se migran retroactivamente o se dejan como histórico intencional.

### 8.3 Refactors

**8.3.1 PUT atómico planeación + cantidades (Opción A)** — hoy la planeación y sus cantidades se guardan en dos pasos separados. Se decidió unificarlos en un único PUT atómico, pero DIFERIDO para después de pruebas; los endpoints actuales se mantienen intactos para no romper el flujo de pruebas.

**8.3.2 Wrapper `CampoSiNo`** — componente envoltorio que centralice permiso por etapa + variante + estado de bloqueo, en vez de repetir `soloLectura`/`disabled` en ~25 campos de `PaginaEditarDom.jsx`. Post-pruebas.

**8.3.3 Centralizar el sistema de toasts** — hoy `Toast.jsx` es solo presentacional (éxito, controlado); cada página replica su propio estado `exito` + helper `mostrarExito` con el `setTimeout` de duración (3 copias: `PaginaEditarDom`, `PaginaClientes`, `PaginaProductos`). Además no hay toast de error (los errores van por `ModalMensaje` o texto rojo inline, según la página). Mejora: un `useToast` (hook) o `ToastProvider` (context) que centralice estado + duración y soporte variantes éxito/error, para que cualquier página dispare `toast.exito(...)` / `toast.error(...)` desde una sola fuente de verdad. Post-pruebas.

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
