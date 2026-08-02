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
| 5 | Cronómetro | Validado — backend; falta política de olvidados (8.1.3) |
| 6 | Dashboard / Reportes | **En corrección (Bloque 1.0)** — el backend responde, pero los veredictos son incorrectos (ver 5.6). Las 3 páginas de informes del frontend son *placeholders* de 7 líneas |

> **Sobre las referencias de línea de este archivo.** Se desplazan con cada cambio y envejecen mal. Verificadas contra código el **2026-08-02**; cuando no cuadren, buscar por el nombre del símbolo, que es lo estable.

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

> **Atenuante confirmado el 2026-08-02 — esta limitación es menos grave de lo que dice el párrafo anterior.** La aplicación está concebida de modo que **cada turno abre su propio cronómetro**: una producción que cruza turnos genera un `RegistroProduccion` nuevo, no un cronómetro más largo. Verificado en base: **ningún `RegistroProduccion` tiene más de un cronómetro** (0 de 52), y el caso de los registros 72 y 73 —dos producciones de la misma planeación 87, un cronómetro cada una— es la demostración del mecanismo. Como el cambio de operarios ocurre entre turnos, y entre turnos hay dos cronómetros distintos con su propio número de personas, el escenario roto se reduce a que alguien se ausente a mitad de turno. Baja la prioridad de 8.1.1 de forma importante.
>
> *(Descartado el mismo día: la hipótesis de que `minutos_asignados` se sobrescribía con varios cronómetros por registro. El camino existe en el código —`models.py:842` asigna, no acumula— pero **nunca se recorre**. Angel lo señaló y los datos le dieron la razón.)*

### 5.6 Predicado único de cumplimiento — `server/cumplimiento.py` (2026-08-02)

Módulo nuevo que responde "¿esta etapa cumplió?" en un solo lugar. Vive **fuera de `views.py`** a propósito: en las vistas la regla sólo existe si alguien abre una pantalla; en módulo aparte queda disponible para informes, migraciones y tareas. **Todavía no lo llama nadie** — el cableado es la F3.4.

**El vocabulario son cuatro etiquetas, no dos.** La distinción que importa es entre las dos últimas:
- `PENDIENTE` — no hay dato. Es legítimo y **el tiempo lo resuelve solo**: el DOM avanza de etapa y deja de estar pendiente.
- `ANÓMALO` — hay dato pero no es creíble. **El tiempo no lo resuelve**; exige que una persona intervenga.

Ninguno entra al denominador del porcentaje, pero salen por razones opuestas y con acciones distintas. Si se mezclan, las anomalías se esconden en la bolsa de pendientes y no las revisa nadie — que es lo que pasó con los cronómetros de los DOM #60 y #102 durante meses.

**PENDIENTE significa cosas distintas en la base de pruebas y en producción — y esto cambia lo que debe decir la pantalla.** En la base actual es un **hueco de captura**: se sembró para probar corrección técnica, no el flujo, así que hay DOMs con etapas que nunca se abrieron. En producción va a ser un **DOM en tránsito**: no ha llegado a esa etapa todavía. Lo primero acusa al usuario de no hacer su trabajo; lo segundo describe una operación funcionando. **Consecuencia práctica: no calibrar la presentación mirando la cobertura de la base de pruebas** (hoy entre 12 % y 67 % según la etapa), porque en producción va a ser alta y el número dejará de necesitar disculpa. *(Discutido el 2026-08-02; el planteamiento es de Angel.)*

**Reglas del agregador, decididas el 2026-07-30** (viven en `project_informes_vs_dashboard`, se traen aquí porque son la especificación de la F3.2):
- **`EN_CURSO` como consolidado nuevo:** hay pendientes y **ningún** incumplimiento. Distingue "va bien pero no ha terminado" de "algo falló". `PARCIAL` se reserva para cuando existe al menos un NO CUMPLIÓ real mezclado con cumplimientos. Con lo anterior, **EN_CURSO va a ser el estado más frecuente en producción**, porque en cualquier momento la mayoría de la base está en vuelo.
- **Los PENDIENTE salen del denominador** y su conteo se muestra al lado.
- **Nota aclaratoria en pantalla**, concreta, del estilo *"solo mide DOMs ya diligenciados"*. Pedida expresamente por Angel y **aplica también al dashboard** (decidida tras ver el 4.5 %). Un porcentaje sin su base a la vista se lee como una afirmación más fuerte de lo que es.

**Los campos que produce cada veredicto** (todo lo demás es captura, no medición): almacén → `dom_realizado_planeacion` · producción → `segun_planeacion` · tratamiento → `tratamiento_segun_planeacion` · despacho → `dom_entregado_ok` · tiempo → los cronómetros del registro.

**Umbrales del cronómetro:** máximo 600 min (10 h) porque la jornada larga son 9 h y **cada turno abre su propio cronómetro**, así que una corrida no cruza turnos; la hora restante es margen para cerrarlo. Mínimo 1 min porque la implausibilidad tiene dos extremos: 41 h es increíble y 6 segundos también. Son máximas de la experiencia — en el código va escrito el razonamiento, no sólo el número.

**El veredicto de producción es de dos columnas (decisión de Angel, 2026-08-02).** El porcentaje oficial lo da `segun_planeacion` (lo que declara el líder); `cumplimiento_produccion` (lo que calculan los números) viaja al lado como contraste y **no se agrega**. Cuando difieren, esa diferencia es la señal: es lo único que permite detectar que `tiempo_produccion_unitario` se desactualizó.

**Multiplicidad — el informe debe recorrer todos los registros, verificado en base el 2026-08-02.** No es un caso de borde: **20 de 58 DOMs tienen más de una planeación** (14 con dos, 5 con tres, 1 con cuatro) y 6 no tienen ninguna. Y una planeación puede tener más de un registro hijo: 4 planeaciones con dos almacenes, 5 con dos o tres producciones, 2 con dos tratamientos. Cualquier agregación que asuma un registro por planeación, o una planeación por DOM, está mal.

**Efecto medido del predicado nuevo** (base de pruebas, 2026-08-02, antes de cablear): producción pasa de **46 incumplimientos a 3** más 43 pendientes; despacho de 51 a 2 más 49 pendientes; tratamiento de 15 a 3 más 12; almacén de 24 a 13 más 11. El informe decía "53 de 58 incumplieron"; con pendientes fuera del denominador la producción queda en 66.7 % (6 de 9 evaluables).

## 6. Seguridad y Entorno

- Las credenciales de BD y `SECRET_KEY` se leen desde `.env` via `python-decouple` (`config()`)
- `.env` está excluido del repositorio — nunca debe commitearse
- El `.gitignore` cubre: `node_modules`, `venv/`, `.venv/`, `.env` **y `.env.*` con excepción explícita `!.env.example`**, `__pycache__/`, `*.pyc`, `*.pyo`, `client/dist`, `client/node_modules`, `staticfiles/`, `*.log`, `logs/`, `.vscode/`, `.idea/`. Ya **no** incluye `*.sqlite3` — se retiró por política de clean code, la base es PostgreSQL y el archivo se borró del disco

### 6.1 Revisión de seguridad — 2026-08-02

Lo verificado y correcto: las **43 vistas declaran `permission_classes`**, todas las escrituras verifican rol, los borrados de catálogo son lógicos y no físicos, las FK importantes usan `RESTRICT` (borrar un cliente no se lleva sus DOMs), el token caduca por inactividad y las contraseñas se hashean. Lo que sigue son huecos concretos, **acordado hacerlos todos**.

**A. Sin límite de intentos de login — alta.** `LoginView` es `AllowAny`, no hay throttling en `REST_FRAMEWORK` y **los intentos fallidos no se registran en ningún lado**. Criterio acordado el 2026-08-02:

- **Sólo cuentan los fallos, y un ingreso correcto pone el contador en cero.** Contar todos los intentos bloquearía a quien entra y sale seis veces en quince minutos sin haberse equivocado. Limpiar al acertar evita que un contador viejo bloquee más tarde a quien ya se identificó bien.
- **Cinco fallos por nombre de usuario cada quince minutos.** Por usuario y no por IP: la oficina sale por una sola IP pública, así que limitar ahí dejaría fuera a todos por culpa de uno.
- **La clave es el nombre escrito, exista o no, y el comportamiento debe ser idéntico en los dos casos.** Si sólo se bloqueara a los usuarios reales, esa diferencia revelaría cuáles nombres existen. Hoy `LoginView` ya devuelve el mismo mensaje para ambos; el límite tiene que respetar esa simetría.
- **Además un tope grueso por IP (~30/min).** El límite por usuario atrapa a quien machaca contraseñas contra una cuenta; no atrapa a quien prueba mil nombres una vez cada uno. Eso lo atrapa el tope por IP. Son complementarios.
- **Es ventana temporal, no bloqueo de cuenta.** Bloquear hasta que un administrador libere suena más seguro y es peor: cualquiera dejaría sin servicio a toda la empresa fallando cinco veces contra cada usuario.
- **El throttling nativo de DRF no sirve tal cual** — cuenta todas las peticiones, no los fallos. Hace falta una pieza propia: contador en caché por usuario, sube cuando `authenticate` devuelve nulo y se borra cuando devuelve usuario. ~30-40 líneas, **1-1.5 h**, no una línea de configuración.

**B. La política de contraseñas de `settings.py` no se ejecuta nunca — alta.** `AUTH_PASSWORD_VALIDATORS` está bien declarado, pero los validadores de Django sólo corren si se los invoca. Los tres serializers (`CrearUsuarioSerializer`, `CambioPasswordSerializer`, `RestablecerPasswordSerializer`) validan a mano: mínimo 8 y "no todo numérico". `CommonPasswordValidator` y `UserAttributeSimilarityValidator` están ahí sin hacer nada, y hoy se acepta `Mudar2026`. Arreglo: llamar `validate_password` en los tres. **Es la misma familia que 8.3.4: código que aparenta un comportamiento que no ocurre.**

**C. Falta `DEFAULT_PERMISSION_CLASSES` — media, defensa en profundidad.** Ninguna vista actual lo olvida, pero el valor por omisión de DRF es `AllowAny`: la primera vista futura sin la línea queda pública y nada avisa.

**D. La auditoría no registra IP ni agente — media.** Sin eso no se reconstruye un incidente. Va junto con 8.1.2.

**E. `coreapi` en `INSTALLED_APPS` sin usarse — baja.** Única mención en todo el proyecto: `settings.py:43`. Paquete sin mantenimiento activo. Quitar de ahí y de `requirements.txt`.

**F. HSTS en 1 hora — baja, no es código.** Subir a un año el día del despliegue, con el certificado ya estable.

**Riesgo aceptado explícitamente, no se arregla:** el token vive en `localStorage` y cualquier XSS lo leería. Buscados `dangerouslySetInnerHTML`, `innerHTML` y `eval` en todo el frontend: **cero coincidencias**, y React escapa por defecto, así que hoy no existe la vía de entrada. Moverlo a cookie `httpOnly` implica rehacer la autenticación completa. **Revisar sólo si algún día se introduce renderizado de HTML.**

**Hallazgo menor:** la rama `if not user.is_active` de `LoginView` es **código muerto**. El backend por defecto de Django ya devuelve nulo para usuarios inactivos, así que el `403` con "Usuario inactivo, contacte al administrador" no lo lee nadie — el usuario inactivo recibe el 401 genérico. No es un problema de seguridad; es un mensaje escrito para ayudar que nunca llega.

### 6.2 El respaldo son cinco piezas, no una

Un respaldo de base de datos **no restaura un sistema**. Lo que devuelve MUDAR al aire son cinco cosas, y tener cuatro de cinco no sirve mucho más que tener cero:

1. **Los globales del clúster** — `pg_dumpall --globals-only`. `pg_dump` respalda *una base*; los roles y sus contraseñas viven por encima. **Contiene los hashes de las contraseñas**: se cuida como el `.env`.
2. **El `.dump` de `mudar_db`** — `pg_dump -F c`. Restaurar los globales **primero**, o falla por dueño inexistente.
3. **El `.env`** — no está en el respaldo ni en git, por diseño. Copia cifrada aparte.
4. **El código** — está en git, ya resuelto.
5. **Qué paquetes tenía el servidor.**

**"Verificado" significa que la aplicación arrancó sobre el respaldo restaurado**, no que `pg_restore` terminó sin error. Procedimiento: `pg_restore --list` para descartar archivo corrupto sin restaurar nada · restaurar en una base **nueva**, jamás encima de la viva · contrastar conteos conocidos · levantar la app contra esa base y comparar el dashboard · borrar la base de verificación · **anotar cuánto tardó**, que es el tiempo real de caída que se le promete al cliente. Repetir cada tres meses y después de cada cambio grande de esquema. Un respaldo que nunca se restauró es una hipótesis.

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

**8.1.1 Cambio de operarios a mitad de la producción** — ⚠️ **prioridad rebajada el 2026-08-02: cada turno abre su propio cronómetro, así que el escenario roto se reduce a una ausencia a mitad de turno. Ver el atenuante de 5.5.** La fórmula `minutos_hombre_produccion_dom = minutos_asignados × numero_personas_asignadas` asume un único valor de personas para toda la duración (ver 5.5). Mejora potencial: registrar segmentos de tiempo con su respectivo `numero_personas_asignadas` y sumar `minutos_hombre` por segmento, en lugar de un único producto global. No priorizado — el flujo actual (confirmar personas antes de iniciar y no cambiarlas durante la producción) es suficiente para el negocio hoy.

Relacionado (pendiente post-pruebas, 2026-07-12): analizar y establecer un mecanismo que **permita modificar `numero_personas_asignadas` (incluso mid-turno) recalculando correctamente** las métricas derivadas (`minutos_hombre_produccion_dom`, `minutos_restantes_dom`, `cumplimiento_produccion`). Como guardarraíl temporal, el frontend bloquea el campo una vez confirmado en el modal (P6), justamente porque hoy no existe ese recálculo.

**8.1.2 Auditoría de eventos y usuario que finaliza** — `RegistroTiempoProduccion` tiene un único campo `usuario` que se escribe solo al INICIAR (`CronometroIniciarView`). Al finalizar (`CronometroFinalizarView`) no se registra quién finalizó, y las vistas del cronómetro (Iniciar/Pausar/Reanudar/Finalizar) no llaman a `registrar_auditoria`. Por lo tanto, si un LIDER_PLANTA inicia y otro finaliza, el segundo no queda registrado en ningún lado. Enfoque acordado (opción 3): registrar auditoría por cada evento de cronómetro. Diferido post-pruebas y condicionado a la decisión del control de crono por usuario creador. Se implementará junto con 8.1.3.

> **Súmese aquí la IP y el agente** (hallazgo D de 6.1): `AuditoriaDom` no los registra, y sin eso no se reconstruye un incidente en producción. Tocan el mismo código, así que se hacen juntos.
>
> **Consecuencia visible hoy:** las producciones 57 y 58, donde se crearon cronómetros de prueba el 2026-08-02, **no figuran como tocadas en ningún informe de auditoría**, porque las cuatro vistas del cronómetro no escriben una sola fila.

**8.1.3 Cronómetros olvidados — POLÍTICA DECIDIDA el 2026-08-02.**

**Llegar al tope no es perder confianza en el dato: es la prueba de que nadie cerró el cronómetro.** La jornada máxima son 540 min (9 h) y el líder debe cerrar antes de terminar el turno; la hora restante es el margen para alcanzar a hacerlo. Cruzar el tope demuestra el olvido. *(Distinción planteada por Angel. La redacción anterior lo trataba como sospecha, que es más débil y lleva a un flujo de resolución equivocado.)*

**La regla:** al cumplirse el tope el sistema **detiene el cronómetro automáticamente** y el registro queda marcado como **ANÓMALO**. Se detiene —en vez de sólo marcarlo— para impedir que siga inflándose indefinidamente.

**El tope se mide sobre TIEMPO NETO, no sobre reloj de pared.** Es el punto que más costó y conviene no perderlo. Con reloj de pared, las pausas se comen el margen y llegan a destruir datos buenos. Jornada de 9 h que arranca a las 06:00:
- *Pausa de 1 h* → neto 9 h, reloj de pared 10 h a las 16:00. El tope dispara **en el mismo instante** en que la persona termina: margen cero.
- *Pausa de 2 h* → neto 9 h, fin real a las 17:00, pero el tope sobre reloj de pared dispara a las **16:00**, una hora **antes**. El sistema detendría un cronómetro vivo y borraría la última hora de producción real.

Sobre neto, las pausas no consumen margen: los topes caerían a las 17:00 y 18:00, siempre una hora después del fin legítimo, se haya pausado lo que se haya pausado.

- **`fin = inicio + 600 min + pausas acumuladas`.** Nunca `fin = ahora`: con `ahora` el valor guardado depende de cuándo se le ocurra correr al proceso —el mismo cronómetro daría 600 min si corre esa noche y 44.260 si corre tres semanas después—, o sea que lo determinaría la infraestructura y no la planta. **Es contabilidad, no medición**: está acotado y es reproducible, y no pretende estimar nada, porque de hecho sobreestima (la producción real terminó a lo sumo al final del turno).
- **Campo nuevo `cerrado_automaticamente`, y de ahí sale la anomalía** — no de comparar `minutos_totales` contra el umbral. Dos razones. Una: `minutos_totales` descuenta pausas, así que un olvidado con 90 min de pausa daría 510 y **escaparía** a cualquier regla de umbral. Dos: lo que se registra no es "este número es sospechoso" sino "**este cronómetro no lo cerró nadie**" — un hecho, no una inferencia sobre un valor.
- **ANÓMALO no entra en `ESTADO_CHOICES`.** `estado` describe lo que el usuario hizo; nadie "hace" una anomalía. Es juicio derivado y vive en `server/cumplimiento.py`.
- **Un cronómetro anómalo no aporta a ninguna métrica**; el veredicto de tiempo devuelve ANÓMALO en vez de un número.
- **PAUSADO necesita regla propia.** Si el tope corre sobre neto y el neto no avanza en pausa, un pausado y olvidado **nunca llega al tope**: se congela para siempre. La regla natural es sobre la **duración de la pausa abierta** — una pausa que dura más que lo que queda de jornada no es pausa, es abandono. Agrava que `CronometroFinalizarView` exige `EN_CURSO`, así que ese registro no se puede ni cerrar.
- **La resolución humana es reemplazar, no confirmar.** Nadie puede validar unas horas que por regla no pudieron ocurrir: el líder dice a qué hora terminó realmente, o anula. Necesita persistir quién revisó y qué decidió.

**Verificado en código el 2026-08-02:** `total_segundos_pausados` **sólo se acumula al reanudar** (`views.py:3616`) y `PausaTiempoProduccion.save()` calcula `segundos_pausados` sólo si hay `fin_pausa` — **la pausa abierta no está en ningún acumulador**. Consecuencias: (a) para evaluar el tope en vivo hay que restar además la pausa abierta; (b) como el tope sólo dispara sobre EN_CURSO, y finalizar exige EN_CURSO, en ese instante no hay pausa abierta y `total_segundos_pausados` está completo — por eso la fórmula del `fin` es calculable sin ambigüedad.

**Evidencia que originó todo esto:** los cronómetros de #60 y #102 estuvieron abiertos meses **sin corromper nada**, porque el informe filtra por `estado='FINALIZADO'`. Se volvieron dañinos al cerrarlos a mano el 2026-08-01: se les calculó el reloj de pared y quedaron en **44.260 y 31.202 minutos**, que desde entonces sí entran en `tiempo_real_total`. No inventaron un número raro — escribieron fielmente el reloj de pared, y el reloj de pared de un cronómetro olvidado no tiene relación con lo que se produjo. **Cerrar automáticamente con `ahora` habría reproducido exactamente ese daño.**

**Reparto por fases** (el orden es dependencia real, no conveniencia):
1. **Detección — F3.3, ahora.** El predicado devuelve ANÓMALO y el veredicto de tiempo deja de contar esos registros. Sólo lectura: sin migración, sin proceso programado, sin servidor. Es lo que detiene el daño. ~2 h, dentro del estimado de la F3.
2. **Cierre automático — en el despliegue.** Migración del campo, comando de Django y **`cron` en el servidor**, que todavía no existe. ~3-4 h.
3. **Resolución humana — con el panel de cronómetros activos** del dashboard (pedido por el cliente en el demo del 2026-07-10).

**8.1.4 Un cronómetro de cero minutos no escribe `minutos_asignados`** *(defecto nuevo, 2026-08-02)* — `models.py:841` dice `if self.estado == 'FINALIZADO' and self.minutos_totales:` y **cero es falso en Python**, así que una corrida de menos de un minuto finaliza sin escribir nada y el registro queda indistinguible de uno que nunca se cronometró. Misma familia que el `all()` de los veredictos, y ya está bien resuelta en la salvaguarda de cierre, que usa `is None` justamente para que el falso y el cero sigan siendo respuestas válidas. Arreglo: `is not None`, una línea. **En la base de pruebas hay 18 cronómetros así**, y por eso hasta hoy eran invisibles.

### 8.2 Datos

**8.2.1 Tolerancia del `<select>` de duración de turno a valores fuera de `choices`** — `PaginaEditarDom.jsx:361` carga el valor guardado en un `<select>` cuyas opciones son solo las vigentes (`OPCIONES_MINUTOS`, `:39-42`). Si el registro trae una duración de una legislación anterior, ninguna opción coincide y **el campo se muestra vacío**. No afecta a producción hoy (la base arranca vacía y todo lo escrito tras la 0019 es válido), pero **el próximo cambio de legislación reproduce la situación con datos reales**. Arreglo: inyectar el valor actual como opción adicional. ~20-30 min, va al bloque de endurecimiento previo al piloto.

> ✅ **CERRADO el 2026-08-01 — la migración retroactiva de turnos 480/600 → 420/540 NO se hace, y no era deuda técnica.** Los 480/600 son el registro fiel de jornadas que de verdad duraban 8 y 10 horas antes del cambio de legislación. Verificado: las **29** filas fuera de `choices` se crearon **todas antes** de la migración 0019, y las **5** posteriores están las 5 en 420/540 — el camino de escritura no ha admitido un solo valor inválido. Además, en producción la base arranca vacía.
>
> ⛔ **Retractada la advertencia del 2026-07-31** que decía que el catálogo `Turno` alimentaba la validación de capacidad: **es falsa**. La capacidad sale siempre de `RegistroTurnoDia` — `capacidad_turno_dia` (`models.py:414`) y `preview_capacidad` (`models.py:175`). Grep de `turno.minutos_totales` en todo el proyecto: cero coincidencias. `Turno.minutos_totales` (480 en pk 1 y 3) es dato muerto que solo aparece en su `__str__`; queda pendiente decidir si se corrige o se elimina el campo.

**8.2.2 Los 13 "no cumplió" de almacén no los escribió nadie** *(hallazgo 2026-08-02)* — `RegistroAlmacen.dom_realizado_planeacion` fue `default=False` hasta la **migración 0017, aplicada el 2026-07-06**, que lo volvió `null=True, default=None`. Todo registro creado antes nació en falso sin que nadie respondiera. Dos evidencias independientes: **11 de los 13 falsos se crearon antes de ese corte**, y en las 680 filas de `AuditoriaDom` el campo fue escrito a verdadero 8 veces y **a falso cero veces**. Ninguna persona ha marcado nunca que almacén incumplió.

Efecto: el 40.9 % de cumplimiento de almacén **no es real**; descontando los falsos fantasma queda en 100 % sobre 9 evaluables. Los otros tres veredictos sí tienen rastro y coinciden con lo que planearon las oleadas — producción en falso en los DOM 96, 100 y 102; tratamiento en 63, 70 y 99; despacho en 67 y 68.

**Es la misma enfermedad que el predicado vino a curar, una migración más atrás**: arreglamos que el nulo contara como incumplimiento, pero no se puede arreglar que el falso cuente como incumplimiento, porque el falso *es* una respuesta legítima. **No se corrige y no es deuda:** en producción la base arranca vacía y cada valor lo escribirá una persona por la aplicación. Queda documentado para que nadie vuelva a leer ese 40.9 % como un dato.

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
