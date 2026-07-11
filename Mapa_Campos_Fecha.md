# Mapa de campos tipo fecha — Mudar

Mapa completo de **todos los campos tipo fecha**, de qué se alimenta cada uno y dónde se usa,
en las tres pantallas (Dashboard, Lista de DOMs, Editar DOM) + backend. Se separan las fechas
de **negocio** de las de **metadata**.

---

## A. Fechas de entrega / negocio (las que importan para el criterio)

### 1. `fecha_solicitada_cliente` — `Dom` (models.py:245, **obligatoria**, sin null)
Fecha que **el cliente** pide la entrega. Se alimenta en **creación (etapa 0)**.

| Dónde | Uso | Editable |
|---|---|---|
| EditarDom `:1203-1206` | "Fecha límite respuesta" (variante administrativa) | ✏️ etapa_0/1 |
| EditarDom `:1284-1287` | "Fecha solicitada cliente" (creación) | ✏️ etapa_0 |
| EditarDom `:1057`, `:1374`, `:2064-2067` | Consolidado / panel etapa2 / Despachos | 🔒 lectura |
| **Dashboard** backend `views.py:3387-3401` | **Criterio de vencidos/próximos/productos 15d** | — |
| Dashboard front `:189` | Se muestra en las alertas | 🔒 |

### 2. `fecha_entrega_pactada` — `Dom` (models.py:262, null OK)
Fecha en que **Mudar se compromete a entregar**. En UI se **etiqueta "planificada"** (deuda técnica
documentada). Se alimenta en **Despachos (etapa 6)**.

| Dónde | Uso | Editable |
|---|---|---|
| EditarDom `:2056-2060` | "Fecha de entrega planificada" | ✏️ etapa_6 |
| EditarDom `:1128` | Consolidado "Fecha de entrega planificada" | 🔒 lectura |
| **ListaDoms** `:128-129`, `:333-352` | **Badge vencido/vence pronto + columna "Fecha entrega"** | — |
| **ListaDoms** filtro "Rango fecha entrega" → `fecha_inicio/fin` (`views.py:1330-1334`) | Filtro | — |
| **ListaDoms** orden "fecha_entrega" + `nivel_urgencia` (`views.py:1348-1366`) | **Criterio de urgencia** | — |

### 3. `fecha_entrega_proyectada` — `Dom` (models.py:267, null OK)
Fecha **proyectada** de entrega según planeación. Se alimenta en **Planeación (etapa 2)**.

| Dónde | Uso | Editable |
|---|---|---|
| EditarDom `:1377-1380` | Panel etapa2 "Fecha de entrega proyectada" | ✏️ etapa_2 |
| EditarDom `:1129`, `:2069-2072` | Consolidado / Despachos | 🔒 lectura |
| Dashboard / ListaDoms | **No se usa hoy** (era el candidato para unificar) | — |

### 4. `fecha_entrega_planificada` — `Dom` (models.py:263) ⚠️ MUERTA
Existe en el modelo pero **retirada de la UI** (comentario en el modelo). Es el "mismo dato" que
pactada según la nota. **No se usa en ninguna de las 3 páginas.** Candidata a limpieza (o dejar como
deuda técnica; quitar una columna es más delicado).

---

## B. Fechas operativas (no de entrega)

### 5. `fecha_planeacion` — `RegistroPlaneacion` (models.py:360)
Fecha planeada para esa producción (por registro de planeación).

| Dónde | Uso | Editable |
|---|---|---|
| EditarDom `:1427-1429` | "Fecha planeación" | ✏️ etapa_2 |
| EditarDom `:1075` | Consolidado | 🔒 |
| EditarDom `:187,213,334...` | Lógica de disponibilidad de turno | — |
| **ListaDoms** filtro "Fecha de planeación" → `registro_planeacion__fecha_planeacion` (`views.py:1336-1340`) | Filtro | — |

### 6. `fecha_asignacion_dom` — `Dom` (models.py:241, `auto_now_add`)
Fecha de creación del DOM. **Siempre solo-lectura.**

| Dónde | Uso |
|---|---|
| EditarDom `:1054`, `:1157`, `:1233` | Display "Fecha asignación DOM" |

### 7. `RegistroTurnoDia.fecha` — (models.py:127)
Fecha del registro de operarios por turno. Uso interno de capacidad; se muestra en la tabla de
auditoría de EditarDom (`:2469` "Turno · Fecha").

---

## C. Metadata (automáticas, no de negocio)
`fecha_creacion` / `fecha_modificacion` (`auto_now_add`/`auto_now`) en casi todos los modelos,
`AuditoriaDom.timestamp`, y las de cronómetro (`inicio`, `fin`, `inicio_pausa`, `fin_pausa`).
No son fechas de entrega — solo trazabilidad.

---

## Observaciones clave (lo que hay que decidir con claridad)
1. **Tres fechas de entrega vivas:** `solicitada` (cliente) · `pactada` (compromiso Mudar, rotulada
   "planificada") · `proyectada` (planeación). Cada una se llena en una etapa distinta.
2. **El criterio de urgencia está partido:** Dashboard → `solicitada`; ListaDoms → `pactada`.
   (Es justo lo que veníamos discutiendo.)
3. **`fecha_entrega_planificada` está muerta** en UI — conviene decidir si se limpia o se documenta
   formalmente.
4. **Doble etiqueta confusa:** el dato `fecha_entrega_pactada` se muestra al usuario como
   **"planificada"** en dos lugares. Data ≠ etiqueta.
5. `fecha_entrega_proyectada` hoy **solo vive en EditarDom**; no aparece en lista ni dashboard.

---

## Decisión en curso (contexto de la sesión 2026-07-09)
El cliente pidió que **`fecha_entrega_proyectada` sea el criterio unificado** para el **dashboard**
y el **cuadro consolidado** de editar DOM:
- **Dashboard:** usar `fecha_entrega_proyectada` con **respaldo a `fecha_solicitada_cliente`** si está
  vacía (`Coalesce`). Cambio pendiente en `views.py` (vencidos/próximos/productos 15d).
- **Consolidado (Ver consolidado):** ya muestra `fecha_entrega_proyectada` y "—" si está vacía
  (`CampoConsolidado` `:2358`) → **sin cambios**.
- **ListaDoms:** queda con `fecha_entrega_pactada` (fuera del alcance acordado) — pendiente de
  confirmar si algún día se alinea también.
