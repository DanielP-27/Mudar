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
| 6 | Dashboard / Reportes | **En corrección (Bloque 1.0)** — los 4 endpoints responden. Veredictos correctos en **1 de 4**: el informe de despacho (`4990402`). Los otros tres siguen contando el nulo como incumplimiento (ver 5.6 y 5.9). Las 3 páginas de informes del frontend son *placeholders* de 7 líneas |

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
> | 6 — Despacho | `dom_liberado_cierre` | `dom_entregado_ok` y `fecha_entrega_pactada` |
>
> ⚠️ **La etapa 4 está declarada en `REQUISITOS_CIERRE` pero NO cableada.** `RegistroProduccionDetalleView.put` conserva su bloque propio (`views.py:3091`), que solo exige el cronómetro. Al cablearla se ganan dos requisitos que hoy no se exigen: el veredicto y el número de personas asignadas. **`segun_planeacion` es hoy el único de los cuatro booleanos de informe que puede quedar en nulo con la etapa cerrada.**
> > *Verificado el 2026-08-05: el `put` **no tiene restricciones de secuencia** —rol, obtener registro, verificar bloqueo, cronómetro, serializer, auditoría, respuesta y nada más—, así que la razón registrada el 2026-08-01 para aplazarlo no se sostiene contra el código. Lo único que se pierde al cablearla es el mensaje específico del cronómetro («Finalice el cronómetro antes de cerrar este registro») a cambio del genérico de `validar_cierre`.*

> **La etapa 2 no tiene campo de veredicto** —produce insumos, no un juicio—, así que su guarda no encaja en el molde de las otras cuatro. Revisada contra código el **2026-08-05**, se parte en **dos mitades con estados distintos**:
>
> - **Mitad A — turno, fecha y existencia del turno-día. VIABLE, ≈1 h, prioridad ANTES del piloto.** El backend ya resuelve valores efectivos a mano (`turno_eval` / `fecha_eval`, `views.py:2226-2230`) y ya rechaza cuando es el primer registro de ese turno-día y faltan operarios o duración (`views.py:2248`). **El hueco exacto es que todo ese bloque vive dentro de `if turno_nuevo or fecha_nueva:`**: un PUT que solo mande `planeacion_completa: true` se lo salta entero, y una planeación con turno y fecha en nulo queda cerrada. Como un `RegistroTurnoDia` no puede crearse sin operarios ni duración, comprobar que existe cubre los cuatro requisitos de una vez. Exige extender la firma de las comprobaciones de `validar_cierre` a `prueba(instancia, datos)` —turno y fecha viajan en el mismo PUT—; hoy solo hay **una** comprobación en todo el mapa (la del cronómetro de la etapa 4, aún sin cablear), así que el cambio es de una línea. **Se hace en la misma sesión que el cableado de la etapa 4**, que comparte esa firma: juntas ≈2,5 h, separadas ≈3,25 h.
> - **Mitad B — al menos un producto con cantidad proyectada. BLOQUEADA. Pasa a deuda técnica (ver 8.3.6).** Depende del refactor 8.3.1.
>
> **Por qué la mitad A es la que importa:** una planeación con fecha y turno pero sin cantidades **sí aparece** en el informe, aportando cero tiempo proyectado — y un cero se ve. La que desaparece de la consulta es la que no tiene fecha (ver 5.7). La mitad barata cierra el daño irreversible; la cara se puede posponer.
>
> ⚠️ **Efecto colateral al aplicarla:** cualquier guion que escriba por API tendrá que mandar turno y fecha. Los de las oleadas hacían PUT directo sin ellos.

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

Módulo nuevo que responde "¿esta etapa cumplió?" en un solo lugar. Vive **fuera de `views.py`** a propósito: en las vistas la regla sólo existe si alguien abre una pantalla; en módulo aparte queda disponible para informes, migraciones y tareas.

> **Estado del cableado al 2026-08-04.** Lo consume **un solo consumidor**: `InformeDespachoView`, desde el commit `4990402`. El informe de cumplimiento, el dashboard y el reporte DOM siguen con `calcular_cumplimiento` y `SIN_DATOS`. `veredicto_tiempo` y la etiqueta `ANÓMALO` **no tienen todavía ningún consumidor**: el suyo es el informe DOM, que está aparcado (ver 5.9).

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

### 5.7 Unidad de conteo de los informes — decidido el 2026-08-02

**Almacén, producción y tratamiento se cuentan por PLANEACIÓN. Despacho por DOM.** El informe mezcla dos unidades **a propósito y correctamente**, porque el veredicto de despacho vive en el `Dom` y no cuelga de ninguna planeación.

**Razón de Angel para quedarse en planeación:** con criterios en lenguaje natural, consolidar por DOM **sesga** la información; con valores numéricos sería distinto. **La pérdida al consolidar es asimétrica:** con números, agregar conserva la magnitud ("3 de 5" sigue diciendo cuánto); con etiquetas, colapsa estados distinguibles en una palabra irreversible — EN_CURSO no dice cuántas jornadas cumplieron ni cuántas faltan.

**Y además distorsiona, no sólo pierde.** El **DOM 67** por DOM da almacén = NO_CUMPLIÓ a secas, que se lee como "a este pedido le falló el almacén". Lo ocurrido: de sus tres planeaciones sólo una llegó a tener registro de almacén, y ese falló. La etiqueta consolidada **afirma más de lo que pasó**.

**Despacho por DOM, y `veredictos_planeacion` lo rechaza con error explícito.** Si se resolviera por planeación, cada una heredaría el mismo veredicto: 2 fallas reales se reportarían como 7. Falla ruidosamente en vez de contar mal en silencio.

**Dos reglas para la pantalla** (bloque de frontend): un DOM con varias planeaciones **ocupa varias filas** — hay que agrupar u ordenar por DOM o se lee como duplicación. Y la sección de despacho **no debe compartir tabla ni encabezado** con las columnas por planeación, o el usuario comparará renglones que no cuentan lo mismo.

**Universo real del informe: 59 de 79 planeaciones.** Las otras **20 no tienen fecha** y el filtro `fecha_planeacion__range` las descarta **en silencio**. `fecha_planeacion` es **nulable por diseño** (`models.py:358`), así que esto **no se cura vaciando la base**: se repetirá en producción. Las 20 tampoco tienen turno, y sin fecha ni turno no hay cálculo de capacidad (`models.py:404`) — están planeadas sólo de nombre.
- **Se decidió NO fecharlas:** son la evidencia de que la app permite ese estado incompleto, y son el caso de prueba del aviso de excluidas. Fecharlas además haría que consumieran capacidad de su turno-día, alterando el `tiempo_restante_dia` de planeaciones del grupo de control.
- ⛔ **Descartado el 2026-08-04:** se había acordado que el informe **declarara lo que excluyó** ("20 planeaciones sin fecha quedaron fuera"). Angel lo retiró del alcance: sobre una base sembrada para ejercitar otras funcionalidades, ese conteo no informa de nada.
  > ⚠️ **No confundir con la regla del nulo, que es permanente y de otra naturaleza.** Un veredicto sin diligenciar **sí entra** al informe, se etiqueta `PENDIENTE` y **sale del denominador**, porque contarlo como incumplimiento atribuye fallas que nadie cometió. Aquí la exclusión es distinta: el registro **no llega siquiera a la consulta**, así que no se ve. El mecanismo que lo produce —campo nulable más filtro por rango— es estructural y se repetirá en producción; su sitio es el bloque de endurecimiento. En despacho el hueco equivalente ya se cerró por la vía correcta: `fecha_entrega_pactada` es requisito de cierre de la etapa 6.
- **Pendiente de Angel, para el bloque de endurecimiento:** ¿es legítimo crear una planeación sin fecha y ponérsela después, o siempre es un error? De eso depende si el campo pasa a obligatorio.
- Los **6 DOMs sin ninguna planeación NO son un hueco**: un pedido nunca planeado no tiene cumplimiento de planeación que reportar.

### 5.8 Informe de despacho — los defectos, con causa exacta (2026-08-02)

> ✅ **LOS TRES ESTÁN CORREGIDOS desde el 2026-08-03, commit `4990402`.** Esta sección se conserva como registro de qué estaba mal y por qué, porque los otros tres informes comparten el mismo molde y van a mostrar los mismos síntomas. **Las referencias de línea son al código ANTERIOR al arreglo** y ya no cuadran con el archivo actual.
>
> **Efecto medido, antes y después, sobre los 7 DOMs del rango:** encabezado y lista dejaron de contradecirse —los 2 nulos pasaron de engrosar la lista de incumplimientos a contarse como `PENDIENTE`—, el denominador bajó de 7 a 5 evaluables y el porcentaje pasó de **42,86 % a 60 %**. El número no subió porque el negocio mejorara: subió porque dejó de castigar a quien todavía no había respondido.

Reproducidos en vivo sobre la base de pruebas, tal como estaban antes del arreglo.

**El "2 contra 4".** `views.py:4134` cuenta `dom_entregado_ok=False` y da 2. Pero el bucle de `:4157` usa `if dom.dom_entregado_ok: ... else: ...`, y ese `else` **atrapa el falso y el nulo juntos**. De 7 DOMs en rango: 3 verdaderos, 2 falsos, 2 nulos → el encabezado dice 2 y la lista trae 4, en la misma respuesta.

**Las tres columnas clonadas.** `views.py:4148`, `:4150` y `:4152` asignan las tres `dom.dom_entregado_ok`: almacén, producción y tratamiento muestran el mismo dato con tres rótulos. Las novedades, igual: la de almacén recibe un campo del DOM y las otras dos un `None` fijo.

**Ceremonia muerta, no inventariada antes.** `views.py:4166-4174` construye una lista de **un solo elemento** y le aplica tres `all(...)`. `cumplimiento_consolidado` siempre acaba igual a `cumplimiento_despacho`. Nueve líneas que no deciden nada.

> ✅ **RESUELTO el 2026-08-03 (commit `4990402`) — la restricción de secuencia ya no existe.** Decía que `ResumenCumplimientoEtapaSerializer` lo compartían los dos informes y que por eso había que cablearlos en un solo paso. Se resolvió por la vía contraria y mejor: **separar los serializers**. Despacho tiene ahora `ResumenDespachoDomSerializer` propio; el compartido quedó con un único usuario y se puede modificar sin coordinar con nada. La propuesta fue de Angel, con el argumento de que son informes distintos que viajan por rutas distintas. Consecuencias: las tres columnas clonadas de despacho **no se arreglaron, dejaron de existir**, y el informe de cumplimiento pasó a poder cablearse solo.

### 5.9 Alcance del módulo de informes — decidido el 2026-08-04

Recapitulación hecha tras contrastar el prompt original (4 informes, 3 formatos de salida) contra el código y contra los esquemas de Descargas.

**Los cuatro informes se parten en dos familias, y el criterio es la naturaleza del dato.** Lo propuso Angel y el código ya estaba partido así sin que nadie lo hubiera notado:
- **Familia booleana — informes 2 (cumplimiento de planeación) y 3 (despacho). SE TRABAJAN AHORA.** Leen cuatro campos del mismo tipo: `dom_realizado_planeacion`, `segun_planeacion`, `tratamiento_segun_planeacion` y `dom_entregado_ok`. Booleanos nulables que diligencia una persona. Mismo predicado, mismo problema del nulo, mismo denominador.
- **Familia numérica — informe 1 (DOM). SE APARCA.** Mide cantidades, minutos y diferencias, con vocabulario propio (`POSITIVO / NEUTRO / NEGATIVO`). Puede quedar **para después de lanzar la V1.0 a pruebas**.
- **Informe 4 (auditoría). SE APARCA.** No tiene veredictos ni denominadores: es un registro de eventos. Queda pendiente revisar su anidación y qué nivel de detalle muestra.

> La confirmación de que la partición es correcta está en `server/cumplimiento.py`: cuatro de sus cinco predicados envuelven `_veredicto_booleano` y sirven a los informes 2 y 3; el quinto, `veredicto_tiempo`, es el único que mira magnitudes, el único que puede devolver `ANÓMALO` y el único **sin consumidor**, porque su consumidor natural es el informe DOM.

**El informe 1 es híbrido, no puramente numérico.** Además de cantidades y minutos calcula los cuatro veredictos de etapa con el mismo `all(...)` sobre los mismos booleanos. Al retomarlo, esa mitad ya está resuelta —es llamar al módulo— y el trabajo real es el veredicto de tiempo, su unidad y qué hacer con `POSITIVO / NEUTRO / NEGATIVO`.

**Bloque 4 del dashboard ("Cumplimiento") — SE DESACTIVA DE LA PANTALLA.** Decisión de Angel. No se corrige: se quita. Dos razones. La visible es que muestra datos imprecisos —los nulos cuentan como incumplimiento—. La de fondo es que **suma cosas que no son sumables**: almacén, producción y tratamiento se cuentan sobre planeaciones, despacho sobre DOMs, y el consolidado (20 de 266, 7,5 %) mezcla los dos denominadores en un solo porcentaje. Corregir el nulo no habría arreglado eso. El bloque nació cerca de la primera demo.
- **Alcance exacto:** solo el bloque de cumplimiento de `PaginaDashboard.jsx`. Totales de DOMs, cantidades, próximos a vencer, vencidos y productos pendientes a 15 días **se quedan**: no dependen de los cuatro booleanos.
- **El backend NO se toca.** `DashboardView` sigue calculando y devolviendo los cinco campos aunque nadie los pinte. Queda cálculo vivo sin consumidor, y por eso está anotado aquí. `SIN_DATOS` y `calcular_cumplimiento` no desaparecen del proyecto: dejan de verse.
- **Se reabre junto con el informe DOM**, no por separado: son la misma familia. **Cuándo —antes o después del despliegue— se decide al terminar los informes 2 y 3, según el tiempo disponible para la V1.0.**

**Exportación a PDF y Excel — APARCADA.** Es un tercio del prompt original (tres formatos para los informes 2, 3 y 4) y **no existe una sola línea en el backend**: búsqueda de `openpyxl`, `reportlab`, `xlsx`, escritura de CSV y `content_type` de PDF en todo `server/` da cero coincidencias. Cuándo se retoma se decide más adelante. No confundir con el PDF del reporte DOM, cuyo "backend listo" solo significa que el endpoint entrega los datos; el archivo se generaría en el frontend con jsPDF.

**El líder sale del esquema del informe de cumplimiento.** El esquema mostraba *"3 jornadas en el rango · Leidy Becerra"* en el renglón del DOM. Los campos existen —`lider_produccion` (`models.py:361`) y `lider_almacen` (`:368`)— pero **son de la planeación, no del DOM**, y ahí está el defecto: medido en base, **8 DOMs con varias planeaciones tienen líderes de producción distintos entre ellas**, así que el renglón tendría que elegir uno y presentarlo como responsable del pedido — la misma distorsión del veredicto consolidado. Además **solo 14 de 79 planeaciones lo tienen diligenciado**. Cuando vuelva, va en el renglón de la jornada.
- **El conteo de jornadas sí se queda.** No es lo mismo: sale gratis de la agrupación y es lo que evita que la repetición del mismo DOM se lea como duplicación (regla de pantalla de 5.7).

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

**E. `coreapi` en `INSTALLED_APPS` — ✅ RESUELTO el 2026-08-06.** Se eliminó junto con las once dependencias que sólo existían para sostenerlo: la mitad de `requirements.txt`, que pasó de 24 paquetes a 12. Era el sistema de documentación de API que DRF deprecó en 2019; su reemplazo actual es `drf-spectacular`, que no reutiliza nada de esto. Verificado antes de quitarlo: los doce nombres de módulo no aparecen ni una vez en el código del proyecto, ninguno tiene un `Required-by` fuera del árbol de `coreapi`, y el orden importa —hay que quitar la línea de `INSTALLED_APPS` **antes** de desinstalar, o Django no arranca.

> **Se van, pero pueden volver.** Reinstalar cualquiera es un `pip install`. Dos merecen nota por si el proyecto crece: **`requests`**, el cliente HTTP estándar de Python, que hará falta el día que la aplicación deba **consumir un servicio externo** (facturación electrónica, notificaciones, pasarelas de pago); y **`uritemplate`**, que DRF pide para generar esquemas OpenAPI si algún día se documenta la API.
>
> ⚠️ **No confundir `requests` con `request`.** `request` —singular, sin `s`— es el objeto que Django entrega a cada vista con la petición **entrante**: `request.data`, `request.user`, `request.query_params`, 148 usos sólo en `views.py`. Viene dentro de Django, no se instala ni se declara. `requests` —plural— es una librería de terceros para **enviar** peticiones HTTP hacia otros servidores, y hoy no se usa en ninguna parte. Se diferencian en una letra y confundirlas es lo más común en Django: la duda es razonable y la respuesta es que borrar la segunda no toca la primera.

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

### 7.4 PLAN DE IMPLEMENTACIÓN — guardas de cierre de etapa (2026-08-05)

> Documento completo en `Descargas/Mudar_Plan_Guardas_Cierre_20260805.docx`. Referencias de línea verificadas contra código el 2026-08-05, HEAD `4990402`.

**Alcance: cuatro piezas. Dos son protección del dato, una es comodidad.**

| Pieza | Estado hoy | Qué compra |
|---|---|---|
| Etapa 2, backend (turno, fecha, turno-día) | No existe | **PROTECCIÓN** |
| Etapa 4, backend | Declarada en el mapa, sin cablear | **PROTECCIÓN** |
| Etapas 3 y 5, backend | Ya cableadas y probadas | Sin trabajo |
| Frontend de almacén, producción y tratamiento | No existe | COMODIDAD |

Despacho queda fuera del pedido; su backend ya está cableado y su caja sería una cuarta pieza de ~30 min.

**Fase 0 — Preparación · 20 min.** Dejar el árbol limpio (hoy `CLAUDE.md` está sin commitear; si el trabajo arranca encima, el diff mezcla documentación con código). Armar el andamio de verificación: **no existe ni un solo archivo de pruebas en el repositorio** —no hay `tests.py`, no hay suite— y los guiones del 1 de agosto vivían en un scratchpad que ya no existe. La verificación es un guion independiente con `APIRequestFactory` + `force_authenticate` envuelto en `transaction.atomic()` con reversión.

**Fase 1 — Extender el mecanismo · 20 min · dificultad 2/10.** `validar_cierre` invoca hoy `prueba(instancia)` (`views.py:232`); pasa a `prueba(instancia, datos)`, y la única comprobación del mapa (cronómetro de etapa 4, `views.py:199`) pasa a `lambda inst, datos:`. **Riesgo casi nulo:** las etapas 3, 5 y 6 tienen la lista de comprobaciones vacía y la etapa 4 no está cableada. Es el momento exacto para cambiar la firma: después habría un camino en producción dependiendo de ella.

**Fase 2 — Guarda de la etapa 2 · 40 min · dificultad 3/10.** Entrada nueva en `REQUISITOS_CIERRE`: candado `planeacion_completa`, campos `turno` y `fecha_planeacion`, comprobación de que existe el `RegistroTurnoDia`. Como un turno-día no se crea sin operarios ni duración, comprobar su existencia cubre los cuatro requisitos de una vez.
> 🔴 **La llamada va DESPUÉS del bloque de turno-día, no antes.** Ese bloque (`views.py:2225-2259`) **crea** el `RegistroTurnoDia` como efecto secundario. Si la validación corriera antes, un PUT que traiga turno, fecha, operarios, duración y el candado todo junto —lo que manda el frontend la primera vez que se usa un turno-día— sería rechazado porque el turno-día aún no existe. Es la trampa del PUT único en su versión más difícil de ver. Sitio correcto: entre la línea 2259 y el `serializer` de la 2296. Los cinco escenarios posibles salen bien ahí, incluido aquel en que el bloque devuelve su propio 400 por falta de operarios y conserva su mensaje específico.
>
> **Detalle:** `valor_efectivo` devuelve tipos heterogéneos —`turno` es un entero desde el payload y un objeto `Turno` desde la instancia; la fecha es cadena o `date`—. **Django acepta las dos formas en un `filter`**, pero conviene comentarlo porque parece un descuido.
>
> **Variante mínima:** solo `turno` y `fecha_planeacion` como campos, sin comprobar el turno-día → la Fase 1 deja de ser necesaria y esta baja a ~20 min. Lo que se pierde: verificado que **el POST de creación no crea el turno-día** (`views.py:2145`), así que una planeación puede nacer con turno y fecha y sin turno-día. Lo que **no** se pierde: esa planeación **sí aparece en los informes**, porque tiene fecha. La variante mínima cubre el agujero que importa; la comprobación del turno-día protege el cálculo de capacidad, que es otra cosa.

**Fase 3 — Cablear la etapa 4 · 30 min · dificultad 3/10.** Quitar el bloque de `views.py:3091-3097` y llamar a `validar_cierre` con `'etapa_4'`. Se gana que `segun_planeacion` deje de poder quedar en nulo con la etapa cerrada y se cierra el hueco de `numero_personas_asignadas` (8 producciones a un clic de cerrarse sin ese dato). Se pierde el mensaje específico del cronómetro a cambio del genérico. **Es la única fase que sustituye un camino en funcionamiento**, por eso va tercera y con verificación ya escrita.

**Fase 4 — Verificación · 50 min.** Doce casos con reversión. Etapa 2: sin fecha · sin turno · sin turno-día · con los tres · el PUT que trae todo junto · un guardado que no intenta cerrar. Etapa 4: sin veredicto · sin personas · sin cronómetro · con los tres · **`False` como veredicto válido**, que es el caso que más fácil se rompe. Etapas 3, 5 y 6: un caso cada una para confirmar que la Fase 1 no las movió.

**Fase 5 — Frontend, las tres cajas · 2,5 a 3 h · dificultad 3/10.** **El patrón ya existe y funciona:** `PaginaEditarDom.jsx:2155-2162` deshabilita el control de bloqueo mientras el cronómetro no esté finalizado y muestra la nota debajo. Ayudante compartido en `CAMPO_BLOQUEO_POR_TIPO` (`:446`), que ya mapea tipo → campo de bloqueo (30 min) · almacén `:1948` (25 min) · tratamiento `:2235` (25 min) · producción (35 min, la única que integra sobre lógica existente) · **pruebas en navegador 1,5 h, y eso domina la fase**: tres etapas × dos caminos + el caso del ADMIN que reabre.
> **Sobre la duplicación de la regla en el frontend:** se acepta, y la razón es que **no es la misma clase de duplicación que `capacidad_turno_dia`**. Allá una divergencia produce un número equivocado en silencio; aquí la copia es solo UX y el backend sigue siendo la garantía. El peor caso es que el control aparezca habilitado y el guardado se rechace: molesto, inmediato y visible. **Nunca corrompe un dato.** Va con un comentario que apunte al backend como fuente de verdad.

**Totales:** backend 2 h 20 min · frontend 2,5-3 h · **5 a 5,5 h, con margen 6 a 7 h**. Si el tiempo se acorta, **el corte natural es después de la Fase 4**: el dato queda protegido y lo que falta es que el usuario se entere antes en vez de después.

**Riesgo y vuelta atrás:** ninguna fase toca el esquema → sin migración, vuelta atrás con `git revert`, datos existentes intactos. ⚠️ **Efecto colateral: cualquier guion que escriba por API tendrá que mandar turno y fecha** — los de las oleadas hacían PUT directo sin ellos.

**Dos decisiones pendientes antes de arrancar:** (1) desactivar el bloque 4 del dashboard, autorización pendiente; (2) comprobación completa del turno-día o variante mínima.

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
> **Dejó de ser solo un refactor de elegancia el 2026-08-05: ahora bloquea la mitad B de la guarda de la etapa 2 (ver 8.3.6 y la nota de 5.1).** Mientras el guardado sea en dos pasos, ninguna validación de cierre puede exigir nada sobre las cantidades.

**8.3.2 Wrapper `CampoSiNo`** — componente envoltorio que centralice permiso por etapa + variante + estado de bloqueo, en vez de repetir `soloLectura`/`disabled` en ~25 campos de `PaginaEditarDom.jsx`. Post-pruebas.

**8.3.3 Centralizar el sistema de toasts** — hoy `Toast.jsx` es solo presentacional (éxito, controlado); cada página replica su propio estado `exito` + helper `mostrarExito` con el `setTimeout` de duración (3 copias: `PaginaEditarDom`, `PaginaClientes`, `PaginaProductos`). Además no hay toast de error (los errores van por `ModalMensaje` o texto rojo inline, según la página). Mejora: un `useToast` (hook) o `ToastProvider` (context) que centralice estado + duración y soporte variantes éxito/error, para que cualquier página dispare `toast.exito(...)` / `toast.error(...)` desde una sola fuente de verdad. Post-pruebas.

**8.3.4 Código muerto que fabrica documentación falsa** — `MINUTOS_HORAS_EXTRAS = 120` (`models.py:9`) **no se usa en ninguna parte** y no existe ningún campo `horas_extras` en ningún modelo. Pero **dos comentarios describen ese comportamiento inexistente**: `models.py:8` y `models.py:121`. Esos comentarios son el **origen del error de la sección 5.3** — quien escribió la documentación leyó el comentario y le creyó, y de ahí pasó a razonamientos posteriores. Es una categoría distinta de las divergencias entre implementaciones: es divergencia **entre la descripción y el código**, y se propaga. Arreglo: borrar la constante y los dos comentarios.

**8.3.5 Revisión de comentarios y declaración de unidades** — barrido de los comentarios existentes en `models.py` y `views.py` para detectar los que describen comportamiento distinto del que implementan, y adición de comentarios donde falta contexto que hoy solo vive en la cabeza de quien lo escribió. Casos concretos ya detectados: el comentario de `minutos_hombre_produccion_dom` (`models.py:700`) describe `tiempo_proyectado`, no la propiedad que encabeza; el `help_text` de `tiempo_produccion_unitario` está **vacío** y debería decir que es el promedio de minutos que **una persona** tarda en una unidad, obtenido de año y medio de registros en papel; `capacidad_turno_dia` no declara que su resultado son minutos-persona (ver 5.4). **La regla:** cuando una propiedad devuelve una magnitud, el comentario debe decir **en qué unidad** y **de dónde sale el dato**. No es documentación por documentar — es que estas confusiones no producen ningún error visible y sobreviven meses.

**8.3.6 Mitad B de la guarda de la etapa 2 — exigir al menos un producto con cantidad proyectada al cerrar la planeación** *(pasa a deuda el 2026-08-05, decisión de Angel)*. Es la única parte de la salvaguarda de cierre que no se puede construir hoy, y no por falta de tiempo sino por dependencia: **`guardarPlaneacion` hace el PUT de la planeación PRIMERO y vuelca las cantidades DESPUÉS** (`PaginaEditarDom.jsx:730-743`), así que en el instante en que el candado llega al backend las cantidades todavía no se han escrito. Una guarda que las exigiera rechazaría un guardado válido y produciría el error más frustrante posible: *«no me deja cerrar aunque acabo de llenar las cantidades»*.

El orden **no es arbitrario** — el comentario del propio código explica que la planeación va primero *«para que el turno-día exista antes de mandar las cantidades»*. Invertirlo rompe la creación del turno-día. **Por tanto esto se desbloquea con 8.3.1, no antes.**

> **Criterio de Angel al diferirlo:** no es un objetivo de reserva para el final de una sesión. Se retoma solo si aparece **un día completo de trabajo antes de producción**; en caso contrario queda como deuda sin fecha de vuelta. El riesgo de intentarlo con prisa es precisamente pisar la trampa del guardado en dos pasos.
>
> **Severidad real: baja.** Una planeación cerrada sin cantidades **sí aparece** en los informes, aportando cero tiempo proyectado. Es un dato pobre, no un dato ausente — a diferencia de la planeación sin fecha, que no llega siquiera a la consulta (5.7) y que sí se cierra ahora con la mitad A.

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
