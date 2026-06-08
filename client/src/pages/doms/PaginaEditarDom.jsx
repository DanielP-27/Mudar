// src/pages/doms/PaginaEditarDom.jsx
import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  FiEye, FiFileText, FiBriefcase, FiPackage,
  FiSettings, FiThermometer, FiTruck, FiPlus
} from 'react-icons/fi'
import { useAutenticacion } from '../../context/AuthContext'
import { puedeEditarEtapa, esSoloLectura } from '../../utils/permisos'
import { toInt } from '../../utils/formatters'
import {
  obtenerDom, actualizarDom,
  obtenerPlaneacion, crearPlaneacion, actualizarPlaneacion,
  actualizarAlmacen, crearAlmacen,
  actualizarProduccion, crearProduccion,
  actualizarTratamiento, crearTratamiento,
} from '../../api/doms'
import { obtenerClientes, obtenerListasPorTipo, obtenerTurnos } from '../../api/catalogos'
import { useDebounce } from '../../hooks/useDebounce'
import TypeaheadInput from '../../components/common/TypeaheadInput'
import CampoFormulario from '../../components/common/CampoFormulario'

// Tipos de DOM administrativos — no llevan etapas de producción
const TIPOS_ADMINISTRATIVOS = ['ADP', 'Documentos']

// Opciones reutilizables para dropdowns booleanos
const OPCIONES_SI_NO = [
  { value: '', label: 'Seleccione una opción' },
  { value: 'true', label: 'Sí' },
  { value: 'false', label: 'No' },
]

// Convierte booleano del backend a string para el select
const boolToStr = (val) =>
  val === true ? 'true' : val === false ? 'false' : ''

// Convierte string del select a booleano para el backend
const strToBool = (val) =>
  val === 'true' ? true : val === 'false' ? false : null

function PaginaEditarDom() {
  const { domId }   = useParams()
  const navegar     = useNavigate()
  const { usuario } = useAutenticacion()

  // Pestaña activa
  const [pestanaActiva, setPestanaActiva] = useState('etapa0')

  // Estado de carga y mensajes
  const [cargando, setCargando]   = useState(true)
  const [guardando, setGuardando] = useState(false)
  const [error, setError]         = useState(null)
  const [exito, setExito]         = useState(null)

  // Datos del DOM — etapas 0, 1 y 6
  const [datosDom, setDatosDom] = useState(null)

  // Planeaciones y registro activo
  const [planeaciones, setPlaneaciones]           = useState([])
  const [idxPlaneacion, setIdxPlaneacion]         = useState(0)

  // Índices de registros hijos activos
  const [idxAlmacen, setIdxAlmacen]       = useState(0)
  const [idxProduccion, setIdxProduccion] = useState(0)
  const [idxTratamiento, setIdxTratamiento] = useState(0)

  // Estado para el flujo de creación de nueva planeación
  const [requiereOperarios, setRequiereOperarios] = useState(false)
  const [numeroOperarios, setNumeroOperarios]     = useState('')

  // Listas para dropdowns
  const [tiposEstadoDom, setTiposEstadoDom]       = useState([])
  const [responsables, setResponsables]           = useState([])
  const [lideresPlanta, setLideresPlanta]         = useState([])
  const [objetivos, setObjetivos]                 = useState([])
  const [empaques, setEmpaques]                   = useState([])
  const [tiposNegociacion, setTiposNegociacion]   = useState([])
  const [turnos, setTurnos]                       = useState([])

  // Typeahead cliente
  const [busquedaCliente, setBusquedaCliente]               = useState('')
  const [sugerenciasCliente, setSugerenciasCliente]         = useState([])
  const [mostrarSugerenciasCliente, setMostrarSugerenciasCliente] = useState(false)
  const textoCliente = useDebounce(busquedaCliente, 300)

  // Determina si el DOM es administrativo
  const esDomAdministrativo = TIPOS_ADMINISTRATIVOS.includes(datosDom?.tipo_estado_dom)

  // ── Carga inicial ──────────────────────────────────────────────────────────
  useEffect(() => {
    const cargarTodo = async () => {
      try {
        const [resDom, resListas] = await Promise.all([
          obtenerDom(domId),
          Promise.all([
            obtenerListasPorTipo('TIPO_ESTADO_DOM'),
            obtenerListasPorTipo('RESPONSABLE'),
            obtenerListasPorTipo('LIDER_PLANTA'),
            obtenerListasPorTipo('OBJETIVO_PLANEACION'),
            obtenerListasPorTipo('EMPAQUE_SERVICIO'),
            obtenerListasPorTipo('TIPO_NEGOCIACION'),
            obtenerTurnos({ activo: true }),
          ])
        ])

        const dom = resDom.data.dom
        setDatosDom(dom)
        setBusquedaCliente(dom.nombre_cliente_detalle ?? '')

        // Cargar planeaciones solo para DOMs productivos
        if (!TIPOS_ADMINISTRATIVOS.includes(dom.tipo_estado_dom)) {
          const resPlaneacion = await obtenerPlaneacion({ dom_id: domId })
          setPlaneaciones(resPlaneacion.data.registros ?? [])
        }

        const [rTipos, rResp, rLideres, rObj, rEmp, rNeg, rTurnos] = resListas
        setTiposEstadoDom(rTipos.data.listas)
        setResponsables(rResp.data.listas)
        setLideresPlanta(rLideres.data.listas)
        setObjetivos(rObj.data.listas)
        setEmpaques(rEmp.data.listas)
        setTiposNegociacion(rNeg.data.listas)
        setTurnos(rTurnos.data.turnos ?? rTurnos.data)

      } catch {
        setError('Error al cargar los datos del DOM.')
      } finally {
        setCargando(false)
      }
    }
    cargarTodo()
  }, [domId])

  // ── Typeahead cliente ──────────────────────────────────────────────────────
  useEffect(() => {
    if (textoCliente.length < 2) return setSugerenciasCliente([])
    obtenerClientes({ nombre: textoCliente, activo: true })
      .then(r => setSugerenciasCliente(r.data.clientes ?? []))
      .catch(() => setSugerenciasCliente([]))
  }, [textoCliente])

  // ── Actualizadores de estado ───────────────────────────────────────────────

  // Actualiza un campo del DOM principal
  const actualizarCampoDom = (campo, valor) =>
    setDatosDom(prev => ({ ...prev, [campo]: valor }))

  // Actualiza un campo de la planeación activa
  const actualizarCampoPlaneacion = (campo, valor) =>
    setPlaneaciones(prev => prev.map((p, i) =>
      i === idxPlaneacion ? { ...p, [campo]: valor } : p
    ))

  // Actualiza un campo de un registro hijo de la planeación activa
  const actualizarCampoHijo = (tipo, campo, valor, idxHijo) =>
    setPlaneaciones(prev => prev.map((p, i) =>
      i === idxPlaneacion ? {
        ...p,
        [`registros_${tipo}`]: p[`registros_${tipo}`].map((h, j) =>
          j === idxHijo ? { ...h, [campo]: valor } : h
        )
      } : p
    ))

  // ── Funciones de guardado ──────────────────────────────────────────────────

  const mostrarExito = (msg) => {
    setExito(msg)
    setTimeout(() => setExito(null), 3000)
  }

  // Guarda etapas 0, 1 y 7 — todas usan PUT /api/doms/<id>/
  const guardarDom = async (mensaje, etapa) => {
    setGuardando(true)
    setError(null)
    try {
      await actualizarDom(domId, {
        ...datosDom,
        etapa,
        nombre_cliente:        toInt(datosDom.nombre_cliente),
        tiempo_salida_almacen: toInt(datosDom.tiempo_salida_almacen),
        rentabilidad:          toInt(datosDom.rentabilidad),
        numero_factura:        toInt(datosDom.numero_factura),
        cantidad_empaques:     toInt(datosDom.cantidad_empaques),
      })
      mostrarExito(mensaje)
    } catch (err) {
      setError(err.response?.data?.error ?? err.response?.data?.detail
        ?? 'Error al guardar los cambios.')
    } finally {
      setGuardando(false)
    }
  }

  // Crea un nuevo registro de planeación para este DOM
  const crearNuevaPlaneacion = async (numOperarios = null) => {
    setGuardando(true)
    setError(null)
    try {
      const payload = { dom_id: domId }
      if (numOperarios) payload.numero_operarios = toInt(numOperarios)
      // console.log se agrega 01-06-26 para revisar problemas en la creación de una nueva planeación
      console.log('payload planeacion:', payload)
      await crearPlaneacion(payload)
      const resPlaneacion = await obtenerPlaneacion({ dom_id: toInt(domId) })
      const nuevas = resPlaneacion.data.registros ?? []
      setPlaneaciones(nuevas)
      setIdxPlaneacion(nuevas.length - 1)
      mostrarExito('Nueva planeación creada correctamente.')
    } catch (err) {
      console.log('error completo:', err)
      if (err.response?.data?.requiere_operarios) {
        setRequiereOperarios(true)
        return
      }
      setError(err.response?.data?.error ?? 'Error al crear la planeación.')
    } finally {
      setGuardando(false)
    }
  }

  // Guarda etapa 2 — planeación activa
  const guardarPlaneacion = async () => {
    const plan = planeaciones[idxPlaneacion]
    if (!plan) return
    setGuardando(true)
    setError(null)
    try {
      await actualizarPlaneacion(plan.id, {
        ...plan,
        cantidad_pedido: toInt(plan.cantidad_pedido),
        orden_produccion:  toInt(plan.orden_produccion),   
        orden_tratamiento: toInt(plan.orden_tratamiento),  
        peso: plan.peso ?? false,   // garantiza boolean, nunca null
      })
      mostrarExito('Planeación guardada correctamente.')
    } catch (err) {
      setError(err.response?.data?.error ?? 'Error al guardar la planeación.')
    } finally {
      setGuardando(false)
    }
  }

  // Guarda registro hijo activo
  const guardarHijo = async (tipo, idx, actualizarFn, campos = {}) => {
    const registros = planeaciones[idxPlaneacion]?.[`registros_${tipo}`]
    const registro  = registros?.[idx]
    if (!registro) return
    setGuardando(true)
    setError(null)
    try {
      await actualizarFn(registro.id, { ...registro, ...campos })
      mostrarExito(`Registro de ${tipo} guardado correctamente.`)
    } catch (err) {
      setError(err.response?.data?.error ?? `Error al guardar el registro de ${tipo}.`)
    } finally {
      setGuardando(false)
    }
  }

  // Crea un nuevo registro hijo
  const crearNuevoHijo = async (tipo, crearFn, setIdx) => {
    const plan = planeaciones[idxPlaneacion]
    if (!plan) return
    setGuardando(true)
    setError(null)
    try {
      const res = await crearFn({ registro_planeacion: plan.id })
      // Recargar planeaciones para reflejar el nuevo registro
      const resPlaneacion = await obtenerPlaneacion({ dom_id: domId })
      const nuevasPlaneaciones = resPlaneacion.data.registros ?? []
      setPlaneaciones(nuevasPlaneaciones)
      // Activar el nuevo registro recién creado
      const nuevaPlaneacion = nuevasPlaneaciones[idxPlaneacion]
      const nuevosRegistros = nuevaPlaneacion?.[`registros_${tipo}`] ?? []
      setIdx(nuevosRegistros.length - 1)
      mostrarExito(`Nuevo registro de ${tipo} creado correctamente.`)
    } catch (err) {
      setError(err.response?.data?.error ?? `Error al crear el registro de ${tipo}.`)
    } finally {
      setGuardando(false)
    }
  }

  // ── Helpers de permisos ────────────────────────────────────────────────────

  const esEditable = (etapa) => puedeEditarEtapa(usuario?.rol, etapa)

  // ── Datos de la planeación y registros hijos activos ───────────────────────
  const planActual        = planeaciones[idxPlaneacion]
  const almacenesActuales = planActual?.registros_almacen    ?? []
  const produccionesActuales = planActual?.registros_produccion ?? []
  const tratamientosActuales = planActual?.registros_tratamiento ?? []
  const almacenActual     = almacenesActuales[idxAlmacen]
  const produccionActual  = produccionesActuales[idxProduccion]
  const tratamientoActual = tratamientosActuales[idxTratamiento]

  // Determina si el último registro hijo está cerrado — habilita "+ Nuevo"
  const ultimoAlmacenCerrado     = almacenesActuales.at(-1)?.dom_realizado_planeacion === true
  const ultimaProduccionCerrada  = produccionesActuales.at(-1)?.cierre_produccion === true
  const ultimoTratamientoCerrado = tratamientosActuales.at(-1)?.tratamiento_completado === true

  // ── Pestañas ───────────────────────────────────────────────────────────────
  const pestanas = esDomAdministrativo ? [
    { id: 'consolidado', icono: <FiEye size={15} />,        label: 'Ver consolidado' },
    { id: 'tramite',     icono: <FiFileText size={15} />,   label: 'Trámite / Documentación' },
  ] : [
    { id: 'consolidado', icono: <FiEye size={15} />,        label: 'Ver consolidado' },
    { id: 'etapa0',      icono: <FiFileText size={15} />,   label: 'Etapa 1 — Creación del DOM' },
    { id: 'etapa1',      icono: <FiBriefcase size={15} />,  label: 'Etapa 2 — Gestión comercial' },
    { id: 'etapa2',      icono: <FiPackage size={15} />,    label: 'Etapa 3 — Planeación' },
    { id: 'etapa3',      icono: <FiPackage size={15} />,    label: 'Etapa 4 — Almacén' },
    { id: 'etapa4',      icono: <FiSettings size={15} />,   label: 'Etapa 5 — Producción' },
    { id: 'etapa5',      icono: <FiThermometer size={15} />,label: 'Etapa 6 — Tratamiento' },
    { id: 'etapa6',      icono: <FiTruck size={15} />,      label: 'Etapa 7 — Despachos' },
  ]

  if (cargando) return (
    <div className="flex items-center justify-center h-64 text-gray-500 text-sm">
      Cargando registro DOM...
    </div>
  )

  if (!datosDom) return (
    <div className="flex items-center justify-center h-64 text-red-500 text-sm">
      No se encontró el registro DOM.
    </div>
  )

  return (
    <div className="max-w-5xl mx-auto">

      {/* Encabezado */}
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-gray-800">
          Editar registro DOM #{datosDom.dom_id}
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          {esSoloLectura(usuario?.rol)
            ? 'Su rol solo permite visualizar la información.'
            : 'Solo puede editar las etapas asignadas a su rol.'
          }
        </p>
      </div>

      {/* Mensajes */}
      {exito && <p className="text-sm text-green-600 mb-4">{exito}</p>}
      {error && <p className="text-sm text-red-600 mb-4">{error}</p>}

      {/* Selector de planeación — solo DOMs productivos con múltiples planeaciones */}
      {!esDomAdministrativo && planeaciones.length > 1 && (
        <div className="mb-4 flex items-center gap-3">
          <span className="text-sm text-gray-600">Planeación:</span>
          {planeaciones.map((p, i) => (
            <button key={p.id} onClick={() => {
              setIdxPlaneacion(i)
              setIdxAlmacen(0)
              setIdxProduccion(0)
              setIdxTratamiento(0)
            }}
              className={`px-3 py-1 text-sm rounded border
                ${idxPlaneacion === i
                  ? 'bg-[#1A56A0] text-white border-[#1A56A0]'
                  : 'border-gray-300 text-gray-600 hover:bg-gray-50'
                }`}>
              Planeación #{i + 1}
            </button>
          ))}
        </div>
      )}

      {/* Sistema de pestañas */}
      <div className="border-b border-gray-200 mb-6 overflow-x-auto">
        <div className="flex gap-0 min-w-max">
          {pestanas.map(p => (
            <button key={p.id} onClick={() => setPestanaActiva(p.id)}
              className={`
                flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2
                transition-colors whitespace-nowrap
                ${pestanaActiva === p.id
                  ? 'border-[#1A56A0] text-[#1A56A0]'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }
              `}>
              {p.icono}{p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Barra de contexto */}
      <div className="flex items-center gap-3 px-4 py-2 mb-4 bg-blue-50 border border-blue-100 rounded text-sm text-blue-800">
        <span className="font-medium">DOM #{datosDom.dom_id}</span>
        <span className="text-blue-300">|</span>
        <span>Cliente: {datosDom.nombre_cliente_detalle ?? '—'}</span>
      </div>

      {/* Contenido de pestañas */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">

        {/* ── Consolidado ─────────────────────────────────────────────────── */}
        {pestanaActiva === 'consolidado' && (
          <div className="space-y-6">
            <SeccionConsolidado titulo="Etapa 1 — Creación del DOM">
              <CampoConsolidado label="Número DOM"           valor={datosDom.dom_id} />
              <CampoConsolidado label="Fecha asignación"     valor={datosDom.fecha_asignacion_dom} />
              <CampoConsolidado label="Cliente"              valor={datosDom.nombre_cliente_detalle} />
              <CampoConsolidado label="Tipo o estado DOM"    valor={datosDom.tipo_estado_dom} />
              <CampoConsolidado label="Fecha solicitada"     valor={datosDom.fecha_solicitada_cliente} />
              <CampoConsolidado label="Responsable"          valor={datosDom.responsable} />
              <CampoConsolidado label="Descripción"          valor={datosDom.descripcion} />
            </SeccionConsolidado>

            {!esDomAdministrativo && (
              <>
                <SeccionConsolidado titulo="Etapa 2 — Gestión comercial">
                  <CampoConsolidado label="Orden de compra"    valor={datosDom.orden_compra} />
                  <CampoConsolidado label="Número cotización"  valor={datosDom.numero_cotizacion} />
                  <CampoConsolidado label="Número factura"     valor={datosDom.numero_factura} />
                  <CampoConsolidado label="Rentabilidad (%)"   valor={datosDom.rentabilidad} />
                  <CampoConsolidado label="Campaña de venta"
                    valor={datosDom.campana_venta ? 'Sí' : 'No'} />
                </SeccionConsolidado>

                {planActual && (
                  <SeccionConsolidado titulo="Etapa 3 — Planeación">
                    <CampoConsolidado label="Fecha planeación"    valor={planActual.fecha_planeacion} />
                    <CampoConsolidado label="Cantidad pedido"     valor={planActual.cantidad_pedido} />
                    <CampoConsolidado label="Planeación completa"
                      valor={planActual.planeacion_completa ? 'Sí' : 'No'} />
                  </SeccionConsolidado>
                )}

                <SeccionConsolidado titulo="Etapa 7 — Despachos">
                  <CampoConsolidado label="Fecha entrega pactada"
                    valor={datosDom.fecha_entrega_pactada} />
                  <CampoConsolidado label="DOM entregado OK"
                    valor={datosDom.dom_entregado_ok ? 'Sí' : 'No'} />
                  <CampoConsolidado label="DOM liberado cierre"
                    valor={datosDom.dom_liberado_cierre ? 'Sí' : 'No'} />
                </SeccionConsolidado>
              </>
            )}
          </div>
        )}

        {/* ── Trámite ADP/Documentos ───────────────────────────────────────── */}
        {pestanaActiva === 'tramite' && (
          <FormEtapa
            titulo="Trámite / Documentación"
            editable={esEditable('etapa_0') || esEditable('etapa_1')}
            guardando={guardando}
            onGuardar={() => guardarDom('Trámite guardado correctamente.', 'etapa_0')}
          >
            <div className="grid grid-cols-2 gap-4">
              <CampoLectura label="Número DOM"          valor={datosDom.dom_id} />
              <CampoLectura label="Fecha asignación DOM" valor={datosDom.fecha_asignacion_dom} />
            </div>

            {/* Tipo DOM — bloqueado para evitar cambio entre administrativo/productivo */}
            <CampoFormulario label="Tipo o estado DOM">
              <select value={datosDom.tipo_estado_dom} disabled
                className="campo-input bg-gray-50 text-gray-500 cursor-not-allowed">
                <option value={datosDom.tipo_estado_dom}>{datosDom.tipo_estado_dom}</option>
              </select>
              <p className="text-xs text-amber-600 mt-1">
                El tipo administrativo no puede cambiarse a productivo.
              </p>
            </CampoFormulario>

            {/* Cliente — typeahead */}
            <CampoFormulario label="Nombre del cliente" obligatorio>
              <TypeaheadInput
                valor={busquedaCliente}
                onChange={e => {
                  setBusquedaCliente(e.target.value)
                  setMostrarSugerenciasCliente(true)
                  actualizarCampoDom('nombre_cliente', '')
                }}
                sugerencias={sugerenciasCliente}
                mostrar={mostrarSugerenciasCliente}
                onSeleccionar={c => {
                  actualizarCampoDom('nombre_cliente', c.cliente_id)
                  setBusquedaCliente(c.nombre_cliente)
                  setMostrarSugerenciasCliente(false)
                }}
                obtenerLabel={c => c.nombre_cliente}
                obtenerKey={c => c.cliente_id}
                placeholder="Digite el nombre del cliente"
                disabled={!esEditable('etapa_0') && !esEditable('etapa_1')}
              />
            </CampoFormulario>

            <CampoFormulario label="Descripción del trámite">
              <textarea value={datosDom.descripcion ?? ''}
                onChange={e => actualizarCampoDom('descripcion', e.target.value)}
                disabled={!esEditable('etapa_0') && !esEditable('etapa_1')}
                rows={3} placeholder="Describa el trámite o procedimiento interno"
                className="campo-input resize-none disabled:bg-gray-50 disabled:text-gray-500" />
            </CampoFormulario>

            <CampoFormulario label="Fecha límite respuesta" obligatorio>
              <input type="date" value={datosDom.fecha_solicitada_cliente ?? ''}
                onChange={e => actualizarCampoDom('fecha_solicitada_cliente', e.target.value)}
                disabled={!esEditable('etapa_0') && !esEditable('etapa_1')}
                className="campo-input disabled:bg-gray-50 disabled:text-gray-500" />
            </CampoFormulario>

            <CampoFormulario label="Responsable" obligatorio>
              <select value={datosDom.responsable ?? ''}
                onChange={e => actualizarCampoDom('responsable', e.target.value)}
                disabled={!esEditable('etapa_0') && !esEditable('etapa_1')}
                className="campo-input disabled:bg-gray-50 disabled:text-gray-500">
                <option value="">Seleccione una opción</option>
                {responsables.map(r => (
                  <option key={r.lista_id} value={r.nombre}>{r.nombre}</option>
                ))}
              </select>
            </CampoFormulario>
          </FormEtapa>
        )}

        {/* ── Etapa 1 — Creación del DOM ───────────────────────────────────── */}
        {pestanaActiva === 'etapa0' && (
          <FormEtapa
            titulo="Etapa 1 — Creación del DOM"
            editable={esEditable('etapa_0')}
            guardando={guardando}
            onGuardar={() => guardarDom('Etapa 1 guardada correctamente.', 'etapa_0')}
          >
            <div className="grid grid-cols-2 gap-4">
              <CampoLectura label="Fecha asignación DOM" valor={datosDom.fecha_asignacion_dom} />
              <CampoLectura label="Número DOM"           valor={datosDom.dom_id} />
            </div>

            {/* Cliente — typeahead */}
            <CampoFormulario label="Nombre cliente" obligatorio>
              <TypeaheadInput
                valor={busquedaCliente}
                onChange={e => {
                  setBusquedaCliente(e.target.value)
                  setMostrarSugerenciasCliente(true)
                  actualizarCampoDom('nombre_cliente', '')
                }}
                sugerencias={sugerenciasCliente}
                mostrar={mostrarSugerenciasCliente}
                onSeleccionar={c => {
                  actualizarCampoDom('nombre_cliente', c.cliente_id)
                  setBusquedaCliente(c.nombre_cliente)
                  setMostrarSugerenciasCliente(false)
                }}
                obtenerLabel={c => c.nombre_cliente}
                obtenerKey={c => c.cliente_id}
                placeholder="Digite el nombre del cliente"
                disabled={!esEditable('etapa_0')}
              />
            </CampoFormulario>

            <CampoFormulario label="Descripción">
              <textarea value={datosDom.descripcion ?? ''}
                onChange={e => actualizarCampoDom('descripcion', e.target.value)}
                disabled={!esEditable('etapa_0')}
                rows={3} placeholder="Información relevante del DOM"
                className="campo-input resize-none disabled:bg-gray-50 disabled:text-gray-500" />
            </CampoFormulario>

            {/* Tipo DOM — permite cambios entre estados productivos, bloqueado a administrativos */}
            <CampoFormulario label="Tipo o estado DOM" obligatorio>
              <select value={datosDom.tipo_estado_dom ?? ''}
                onChange={e => actualizarCampoDom('tipo_estado_dom', e.target.value)}
                disabled={!esEditable('etapa_0')}
                className="campo-input disabled:bg-gray-50 disabled:text-gray-500">
                <option value="">Seleccione una opción</option>
                {tiposEstadoDom
                  .filter(t => !TIPOS_ADMINISTRATIVOS.includes(t.nombre))
                  .map(t => (
                    <option key={t.lista_id} value={t.nombre}>{t.nombre}</option>
                  ))}
              </select>
            </CampoFormulario>

            <CampoFormulario label="Fecha solicitada cliente" obligatorio>
              <input type="date" value={datosDom.fecha_solicitada_cliente ?? ''}
                onChange={e => actualizarCampoDom('fecha_solicitada_cliente', e.target.value)}
                disabled={!esEditable('etapa_0')}
                className="campo-input disabled:bg-gray-50 disabled:text-gray-500" />
            </CampoFormulario>

            <CampoFormulario label="Responsable" obligatorio>
              <select value={datosDom.responsable ?? ''}
                onChange={e => actualizarCampoDom('responsable', e.target.value)}
                disabled={!esEditable('etapa_0')}
                className="campo-input disabled:bg-gray-50 disabled:text-gray-500">
                <option value="">Seleccione una opción</option>
                {responsables.map(r => (
                  <option key={r.lista_id} value={r.nombre}>{r.nombre}</option>
                ))}
              </select>
            </CampoFormulario>

            {datosDom.productos?.length > 0 && (
              <div>
                <p className="text-xs font-medium text-gray-600 uppercase tracking-wide mb-2">
                  Productos del DOM
                </p>
                <table className="w-full text-sm border border-gray-200 rounded overflow-hidden">
                  <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
                    <tr>
                      <th className="text-left px-3 py-2 font-medium">Producto</th>
                      <th className="text-center px-3 py-2 font-medium">Tiempo unitario (min)</th>
                      <th className="text-center px-3 py-2 font-medium">Cantidad pedido</th>
                    </tr>
                  </thead>
                  <tbody>
                    {datosDom.productos.map((p, i) => (
                      <tr key={p.id} className={i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                        <td className="px-3 py-2 text-gray-800">
                          {p.tipo_producto_detalle?.nombre_producto ?? '—'}
                        </td>
                        <td className="px-3 py-2 text-center text-gray-600">
                          {p.tipo_producto_detalle?.tiempo_produccion_unitario ?? '—'}
                        </td>
                        <td className="px-3 py-2 text-center text-gray-600">
                          {p.cantidad_pedido ?? '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </FormEtapa>
        )}

        {/* ── Etapa 2 — Gestión comercial ──────────────────────────────────── */}
        {pestanaActiva === 'etapa1' && (
          <FormEtapa
            titulo="Etapa 2 — Gestión comercial y diseño"
            editable={esEditable('etapa_1')}
            guardando={guardando}
            onGuardar={() => guardarDom('Etapa 2 guardada correctamente.', 'etapa_1')}
          >
            <div className="grid grid-cols-2 gap-4">
              <CampoFormulario label="Orden de compra">
                <input type="text" value={datosDom.orden_compra ?? ''}
                  onChange={e => actualizarCampoDom('orden_compra', e.target.value)}
                  disabled={!esEditable('etapa_1')}
                  className="campo-input disabled:bg-gray-50 disabled:text-gray-500" />
              </CampoFormulario>
              <CampoFormulario label="Número cotización">
                <input type="text" value={datosDom.numero_cotizacion ?? ''}
                  onChange={e => actualizarCampoDom('numero_cotizacion', e.target.value)}
                  disabled={!esEditable('etapa_1')}
                  className="campo-input disabled:bg-gray-50 disabled:text-gray-500" />
              </CampoFormulario>
              <CampoFormulario label="Número factura">
                <input type="number" value={datosDom.numero_factura ?? ''}
                  onChange={e => actualizarCampoDom('numero_factura', e.target.value)}
                  disabled={!esEditable('etapa_1')}
                  className="campo-input disabled:bg-gray-50 disabled:text-gray-500" />
              </CampoFormulario>
              <CampoFormulario label="Rentabilidad (%)">
                <input type="number" value={datosDom.rentabilidad ?? ''}
                  onChange={e => actualizarCampoDom('rentabilidad', e.target.value)}
                  disabled={!esEditable('etapa_1')}
                  className="campo-input disabled:bg-gray-50 disabled:text-gray-500" />
              </CampoFormulario>
              <CampoFormulario label="Tiempo salida almacén (minutos)">
                <input type="number" value={datosDom.tiempo_salida_almacen ?? ''}
                  onChange={e => actualizarCampoDom('tiempo_salida_almacen', e.target.value)}
                  disabled={!esEditable('etapa_1')}
                  className="campo-input disabled:bg-gray-50 disabled:text-gray-500" />
              </CampoFormulario>
              <CampoFormulario label="Campaña de venta">
                <SelectSiNo value={boolToStr(datosDom.campana_venta)}
                  onChange={v => actualizarCampoDom('campana_venta', strToBool(v))}
                  disabled={!esEditable('etapa_1')} />
              </CampoFormulario>
            </div>

            <CampoFormulario label="Validación etapa 1">
              <SelectSiNo value={boolToStr(datosDom.dom_relacionado_produccion)}
                onChange={v => actualizarCampoDom('dom_relacionado_produccion', strToBool(v))}
                disabled={!esEditable('etapa_1')} />
              <p className="text-xs text-amber-600 mt-1">
                Importante: una vez marque Sí y guarde, no podrá realizar
                modificaciones posteriores a esta etapa.
              </p>
            </CampoFormulario>
          </FormEtapa>
        )}

        {/* ── Etapa 3 — Planeación ─────────────────────────────────────────── */}
        {pestanaActiva === 'etapa2' && (
          <>
          {(planeaciones.length === 0 || planActual?.planeacion_completa) && esEditable('etapa_2') && (
            <div className="mb-4 space-y-3">
              {requiereOperarios ? (
                <div className="flex items-end gap-3">
                  <CampoFormulario label="Número de operarios del turno">
                    <input type="number" value={numeroOperarios}
                      onChange={e => setNumeroOperarios(e.target.value)}
                      placeholder="Ingrese número de operarios"
                      className="campo-input" />
                  </CampoFormulario>
                  <button onClick={() => crearNuevaPlaneacion(numeroOperarios)}
                    disabled={!numeroOperarios || guardando}
                    className="px-4 py-2 bg-[#1A56A0] text-white text-sm font-medium rounded
                               hover:bg-[#134080] disabled:opacity-60 disabled:cursor-not-allowed">
                    Confirmar
                  </button>
                  <button onClick={() => { setRequiereOperarios(false); setNumeroOperarios('') }}
                    className="px-4 py-2 border border-gray-300 text-gray-600 text-sm rounded hover:bg-gray-50">
                    Cancelar
                  </button>
                </div>
              ) : (
                <button onClick={() => crearNuevaPlaneacion()}
                  disabled={guardando}
                  className="flex items-center gap-2 px-4 py-2 text-sm font-medium
                             text-[#1A56A0] border border-[#1A56A0] rounded
                             hover:bg-blue-50 disabled:opacity-40 disabled:cursor-not-allowed">
                  <FiPlus size={14} /> Nueva planeación
                </button>
              )}
            </div>
          )}
          <FormEtapa
            titulo="Etapa 3 — Planeación"
            editable={esEditable('etapa_2') && !planActual?.planeacion_completa}
            guardando={guardando}
            onGuardar={guardarPlaneacion}
            sinRegistro={!planActual}
          >
            {planActual && (
              <div className="grid grid-cols-2 gap-4">
                <CampoFormulario label="Fecha planeación">
                  <input type="date" value={planActual.fecha_planeacion ?? ''}
                    onChange={e => actualizarCampoPlaneacion('fecha_planeacion', e.target.value)}
                    disabled={!esEditable('etapa_2')}
                    className="campo-input disabled:bg-gray-50 disabled:text-gray-500" />
                </CampoFormulario>
                <CampoFormulario label="Cantidad pedido">
                  <input type="number" value={planActual.cantidad_pedido ?? ''}
                    onChange={e => actualizarCampoPlaneacion('cantidad_pedido', e.target.value)}
                    disabled={!esEditable('etapa_2')}
                    className="campo-input disabled:bg-gray-50 disabled:text-gray-500" />
                </CampoFormulario>
                <CampoFormulario label="Turno">
                  <select value={planActual.turno ?? ''}
                    onChange={e => actualizarCampoPlaneacion('turno', toInt(e.target.value))}
                    disabled={!esEditable('etapa_2')}
                    className="campo-input disabled:bg-gray-50 disabled:text-gray-500">
                    <option value="">Seleccione una opción</option>
                    {turnos.map(t => (
                      <option key={t.turno_id} value={t.turno_id}>{t.nombre_turno}</option>
                    ))}
                  </select>
                </CampoFormulario>
                <CampoFormulario label="Orden producción dentro de turno y fecha">
                  <input type="text" value={planActual.orden_produccion ?? ''}
                    onChange={e => actualizarCampoPlaneacion('orden_produccion', e.target.value)}
                    disabled={!esEditable('etapa_2')}
                    className="campo-input disabled:bg-gray-50 disabled:text-gray-500" />
                </CampoFormulario>
                <CampoFormulario label="Líder de producción">
                  <select value={planActual.lider_produccion ?? ''}
                    onChange={e => actualizarCampoPlaneacion('lider_produccion', e.target.value)}
                    disabled={!esEditable('etapa_2')}
                    className="campo-input disabled:bg-gray-50 disabled:text-gray-500">
                    <option value="">Seleccione una opción</option>
                    {lideresPlanta.map(l => (
                      <option key={l.lista_id} value={l.nombre}>{l.nombre}</option>
                    ))}
                  </select>
                </CampoFormulario>
                <CampoFormulario label="Objetivo planeación actual">
                  <select value={planActual.objetivo_planeacion ?? ''}
                    onChange={e => actualizarCampoPlaneacion('objetivo_planeacion', e.target.value)}
                    disabled={!esEditable('etapa_2')}
                    className="campo-input disabled:bg-gray-50 disabled:text-gray-500">
                    <option value="">Seleccione una opción</option>
                    {objetivos.map(o => (
                      <option key={o.lista_id} value={o.nombre}>{o.nombre}</option>
                    ))}
                  </select>
                </CampoFormulario>
                <CampoFormulario label="Líder de almacén">
                  <select value={planActual.lider_almacen ?? ''}
                    onChange={e => actualizarCampoPlaneacion('lider_almacen', e.target.value)}
                    disabled={!esEditable('etapa_2')}
                    className="campo-input disabled:bg-gray-50 disabled:text-gray-500">
                    <option value="">Seleccione una opción</option>
                    {lideresPlanta.map(l => (
                      <option key={l.lista_id} value={l.nombre}>{l.nombre}</option>
                    ))}
                  </select>
                </CampoFormulario>
                <CampoFormulario label="Orden de tratamiento termico en turno y fecha">
                  <input type="text" value={planActual.orden_tratamiento ?? ''}
                    onChange={e => actualizarCampoPlaneacion('orden_tratamiento', e.target.value)}
                    disabled={!esEditable('etapa_2')}
                    className="campo-input disabled:bg-gray-50 disabled:text-gray-500" />
                </CampoFormulario>
                <CampoFormulario label="¿Productos deben pesarse?">
                  <SelectSiNo value={boolToStr(planActual.peso)}
                    onChange={v => actualizarCampoPlaneacion('peso', strToBool(v))}
                    disabled={!esEditable('etapa_2')} />
                </CampoFormulario>
                <CampoFormulario label="¿Materias primas disponibles para fabricar este DOM?">
                  <SelectSiNo value={boolToStr(planActual.materia_prima_disponible)}
                    onChange={v => actualizarCampoPlaneacion('materia_prima_disponible', strToBool(v))}
                    disabled={!esEditable('etapa_2')} />
                </CampoFormulario>
                <CampoFormulario label="¿Productos se elaboran con tablilla o madera larga?">
                  <select value={planActual.tablilla_madera ?? ''}
                    onChange={e => actualizarCampoPlaneacion('tablilla_madera', e.target.value)}
                    disabled={!esEditable('etapa_2')}
                    className="campo-input disabled:bg-gray-50 disabled:text-gray-500">
                    <option value="">Seleccione una opción</option>
                    <option value="Madera">Madera</option>
                    <option value="Tablilla">Tablilla</option>
                  </select>
                </CampoFormulario>
                <CampoFormulario label="¿Productos van encartonados?">
                  <SelectSiNo value={boolToStr(planActual.encartonar)}
                    onChange={v => actualizarCampoPlaneacion('encartonar', strToBool(v))}
                    disabled={!esEditable('etapa_2')} />
                </CampoFormulario>
                <CampoFormulario label="¿Productos requieren grafado y elaboración de fundas">
                  <SelectSiNo value={boolToStr(planActual.grafado_fundas)}
                    onChange={v => actualizarCampoPlaneacion('grafado_fundas', strToBool(v))}
                    disabled={!esEditable('etapa_2')} />
                </CampoFormulario>
                <CampoFormulario label="¿Producto requiere Control de tiempo y ensamble en armadora?">
                  <SelectSiNo value={boolToStr(planActual.control_tiempo)}
                    onChange={v => actualizarCampoPlaneacion('control_tiempo', strToBool(v))}
                    disabled={!esEditable('etapa_2')} />
                </CampoFormulario>
                <CampoFormulario label="¿Cliente recoge los productos?">
                  <SelectSiNo value={boolToStr(planActual.cliente_recoge)}
                    onChange={v => actualizarCampoPlaneacion('cliente_recoge', strToBool(v))}
                    disabled={!esEditable('etapa_2')} />
                </CampoFormulario>
                <CampoFormulario label="¿Mudar de Colombia entrega los productos?">
                  <SelectSiNo value={boolToStr(planActual.mudar_entrega)}
                    onChange={v => actualizarCampoPlaneacion('mudar_entrega', strToBool(v))}
                    disabled={!esEditable('etapa_2')} />
                </CampoFormulario>
                <CampoFormulario label="¿Productos requieren tratamiento térmico?">
                  <SelectSiNo value={boolToStr(planActual.tratamiento_termico)}
                    onChange={v => actualizarCampoPlaneacion('tratamiento_termico', strToBool(v))}
                    disabled={!esEditable('etapa_2')} />
                </CampoFormulario>
                <CampoFormulario label="¿Productos deben llevar Sello ICA?">
                  <SelectSiNo value={boolToStr(planActual.sello_ica)}
                    onChange={v => actualizarCampoPlaneacion('sello_ica', strToBool(v))}
                    disabled={!esEditable('etapa_2') || !!planActual?.planeacion_completa} />
                </CampoFormulario>
              </div>
            )}
            {planActual && (
              <CampoFormulario label="¿Registro de planeación completo y relacionado con producción?">
                <SelectSiNo value={boolToStr(planActual.planeacion_completa)}
                  onChange={v => actualizarCampoPlaneacion('planeacion_completa', strToBool(v))}
                  disabled={!esEditable('etapa_2')} />
                <p className="text-xs text-amber-600 mt-1">
                  Importante: una vez marque Sí y guarde, no podrá realizar
                  modificaciones posteriores a esta etapa.
                </p>
              </CampoFormulario>
            )}
          </FormEtapa>
          </>
        )}

        {/* ── Etapa 4 — Almacén ────────────────────────────────────────────── */}
        {pestanaActiva === 'etapa3' && (
          <div className="space-y-4">
            {/* Selector de registro almacén */}
            <SelectorRegistro
              registros={almacenesActuales}
              idxActivo={idxAlmacen}
              onCambiar={setIdxAlmacen}
              etiqueta="Almacén"
              campoCierre="dom_realizado_planeacion"
              ultimoCerrado={ultimoAlmacenCerrado}
              puedeCrear={esEditable('etapa_3')}
              onNuevo={() => crearNuevoHijo('almacen', crearAlmacen, setIdxAlmacen)}
              guardando={guardando}
            />
            <FormEtapa
              titulo="Etapa 4 — Almacén"
              editable={esEditable('etapa_3') && !almacenActual?.dom_realizado_planeacion}
              guardando={guardando}
              onGuardar={() => guardarHijo('almacen', idxAlmacen, actualizarAlmacen)}
              sinRegistro={!almacenActual}
            >
              {almacenActual && (
                <div className="grid grid-cols-2 gap-4">
                  <CampoFormulario label="¿Materias primas internas procesadas?">
                    <SelectSiNo value={boolToStr(almacenActual.materias_primas)}
                      onChange={v => actualizarCampoHijo('almacen', 'materias_primas', strToBool(v), idxAlmacen)}
                      disabled={!esEditable('etapa_3') || almacenActual.dom_realizado_planeacion} />
                  </CampoFormulario>
                  <CampoFormulario label="Tarea asignada de planeación">
                    <input type="text" value={planActual?.objetivo_planeacion ?? '—'}
                      disabled
                      className="campo-input disabled:bg-gray-50 disabled:text-gray-500" />
                  </CampoFormulario>
                  <CampoFormulario label="Novedad cumplimiento almacén">
                    <textarea value={almacenActual.novedad_cumplimiento_almacen ?? ''}
                      onChange={e => actualizarCampoHijo('almacen', 'novedad_cumplimiento_almacen', e.target.value, idxAlmacen)}
                      disabled={!esEditable('etapa_3') || almacenActual.dom_realizado_planeacion}
                      rows={2}
                      className="campo-input resize-none disabled:bg-gray-50 disabled:text-gray-500" />
                  </CampoFormulario>
                  <CampoFormulario label="¿Materias primas liberadas para producción?">
                    <SelectSiNo value={boolToStr(almacenActual.materias_liberadas)}
                      onChange={v => actualizarCampoHijo('almacen', 'materias_liberadas', strToBool(v), idxAlmacen)}
                      disabled={!esEditable('etapa_3') || almacenActual.dom_realizado_planeacion} />
                  </CampoFormulario>
                  <CampoFormulario label="¿Actividades de almacen realizadas según planeación para este DOM?">
                    <SelectSiNo value={boolToStr(almacenActual.dom_realizado_planeacion)}
                      onChange={v => actualizarCampoHijo('almacen', 'dom_realizado_planeacion', strToBool(v), idxAlmacen)}
                      disabled={!esEditable('etapa_3') || almacenActual.dom_realizado_planeacion} />
                    <p className="text-xs text-amber-600 mt-1">
                      Importante: una vez marque Sí y guarde, no podrá realizar
                      modificaciones posteriores a este registro.
                    </p>
                  </CampoFormulario>
                </div>
              )}
            </FormEtapa>
          </div>
        )}

        {/* ── Etapa 5 — Producción ─────────────────────────────────────────── */}
        {pestanaActiva === 'etapa4' && (
          <div className="space-y-4">
            <SelectorRegistro
              registros={produccionesActuales}
              idxActivo={idxProduccion}
              onCambiar={setIdxProduccion}
              etiqueta="Producción"
              campoCierre="cierre_produccion"
              ultimoCerrado={ultimaProduccionCerrada}
              puedeCrear={esEditable('etapa_4')}
              onNuevo={() => crearNuevoHijo('produccion', crearProduccion, setIdxProduccion)}
              guardando={guardando}
            />
            <FormEtapa
              titulo="Etapa 5 — Producción"
              editable={esEditable('etapa_4') && !produccionActual?.cierre_produccion}
              guardando={guardando}
              onGuardar={() => guardarHijo('produccion', idxProduccion, actualizarProduccion, {
                cantidad_elaborada:        toInt(produccionActual?.cantidad_elaborada),
                minutos_asignados:         toInt(produccionActual?.minutos_asignados),
                numero_personas_asignadas: toInt(produccionActual?.numero_personas_asignadas),
              })}
              sinRegistro={!produccionActual}
            >
              {produccionActual && (
                <div className="grid grid-cols-2 gap-4">
                  <CampoLectura
                    label="Producto a elaborar"
                    valor={planActual?.dom_producto_detalle?.tipo_producto_detalle?.nombre_producto}
                  />
                  <CampoLectura
                    label="Tiempo de elaboración unitario (min)"
                    valor={planActual?.dom_producto_detalle?.tipo_producto_detalle?.tiempo_produccion_unitario}
                  />
                  <CampoLectura
                    label="Tiempo proyectado elaboración producto (min)"
                    valor={planActual?.tiempo_proyectado}
                  />
                  <CampoFormulario label="Cantidad elaborada">
                    <input type="number" value={produccionActual.cantidad_elaborada ?? ''}
                      onChange={e => actualizarCampoHijo('produccion', 'cantidad_elaborada', e.target.value, idxProduccion)}
                      disabled={!esEditable('etapa_4') || produccionActual.cierre_produccion}
                      className="campo-input disabled:bg-gray-50 disabled:text-gray-500" />
                  </CampoFormulario>
                  <CampoFormulario label="Minutos asignados">
                    <input type="number" value={produccionActual.minutos_asignados ?? ''}
                      onChange={e => actualizarCampoHijo('produccion', 'minutos_asignados', e.target.value, idxProduccion)}
                      disabled={!esEditable('etapa_4') || produccionActual.cierre_produccion}
                      className="campo-input disabled:bg-gray-50 disabled:text-gray-500" />
                  </CampoFormulario>
                  <CampoFormulario label="Número personas asignadas">
                    <input type="number" value={produccionActual.numero_personas_asignadas ?? ''}
                      onChange={e => actualizarCampoHijo('produccion', 'numero_personas_asignadas', e.target.value, idxProduccion)}
                      disabled={!esEditable('etapa_4') || produccionActual.cierre_produccion}
                      className="campo-input disabled:bg-gray-50 disabled:text-gray-500" />
                  </CampoFormulario>
                  <CampoFormulario label="Tarea asignada de planeación">
                    <input type="text" value={planActual?.objetivo_planeacion ?? '—'}
                      disabled
                      className="campo-input disabled:bg-gray-50 disabled:text-gray-500" />
                  </CampoFormulario>
                  <CampoFormulario label="Novedad cumplimiento producción">
                    <textarea value={produccionActual.novedad_cumplimiento_produccion ?? ''}
                      onChange={e => actualizarCampoHijo('produccion', 'novedad_cumplimiento_produccion', e.target.value, idxProduccion)}
                      disabled={!esEditable('etapa_4') || produccionActual.cierre_produccion}
                      rows={2}
                      className="campo-input resize-none disabled:bg-gray-50 disabled:text-gray-500" />
                  </CampoFormulario>
                  <CampoFormulario label="¿Actividades de producción realizadas según registro de planeación?">
                    <SelectSiNo value={boolToStr(produccionActual.segun_planeacion)}
                      onChange={v => actualizarCampoHijo('produccion', 'segun_planeacion', strToBool(v), idxProduccion)}
                      disabled={!esEditable('etapa_4') || produccionActual.cierre_produccion} />
                  </CampoFormulario>
                  <CampoFormulario label="Producción no completada">
                    <SelectSiNo value={boolToStr(produccionActual.produccion_no_completada)}
                      onChange={v => actualizarCampoHijo('produccion', 'produccion_no_completada', strToBool(v), idxProduccion)}
                      disabled={!esEditable('etapa_4') || produccionActual.cierre_produccion} />
                  </CampoFormulario>
                  <CampoFormulario label="¿Este DOM ya ha sido liberado desde producción?">
                    <SelectSiNo value={boolToStr(produccionActual.cierre_produccion)}
                      onChange={v => actualizarCampoHijo('produccion', 'cierre_produccion', strToBool(v), idxProduccion)}
                      disabled={!esEditable('etapa_4') || produccionActual.cierre_produccion} />
                    <p className="text-xs text-amber-600 mt-1">
                      Importante: una vez marque Sí y guarde, no podrá realizar
                      modificaciones posteriores a este registro.
                    </p>
                  </CampoFormulario>
                </div>
              )}
            </FormEtapa>
          </div>
        )}

        {/* ── Etapa 6 — Tratamiento ────────────────────────────────────────── */}
        {pestanaActiva === 'etapa5' && (
          <div className="space-y-4">
            <SelectorRegistro
              registros={tratamientosActuales}
              idxActivo={idxTratamiento}
              onCambiar={setIdxTratamiento}
              etiqueta="Tratamiento"
              campoCierre="tratamiento_completado"
              ultimoCerrado={ultimoTratamientoCerrado}
              puedeCrear={esEditable('etapa_5')}
              onNuevo={() => crearNuevoHijo('tratamiento', crearTratamiento, setIdxTratamiento)}
              guardando={guardando}
            />
            <FormEtapa
              titulo="Etapa 6 — Tratamiento"
              editable={esEditable('etapa_5') && !tratamientoActual?.tratamiento_completado}
              guardando={guardando}
              onGuardar={() => guardarHijo('tratamiento', idxTratamiento, actualizarTratamiento, {
                numero_tratamiento: toInt(tratamientoActual?.numero_tratamiento),
              })}
              sinRegistro={!tratamientoActual}
            >
              {tratamientoActual && (
                <div className="grid grid-cols-2 gap-4">
                  <CampoFormulario label="DOM con tratamiento">
                    <SelectSiNo value={boolToStr(tratamientoActual.dom_con_tratamiento)}
                      onChange={v => actualizarCampoHijo('tratamiento', 'dom_con_tratamiento', strToBool(v), idxTratamiento)}
                      disabled={!esEditable('etapa_5') || tratamientoActual.tratamiento_completado} />
                  </CampoFormulario>
                  <CampoFormulario label="Número de tratamiento fitosanitario asignado">
                    <input type="number" value={tratamientoActual.numero_tratamiento ?? ''}
                      onChange={e => actualizarCampoHijo('tratamiento', 'numero_tratamiento', e.target.value, idxTratamiento)}
                      disabled={!esEditable('etapa_5') || tratamientoActual.tratamiento_completado}
                      className="campo-input disabled:bg-gray-50 disabled:text-gray-500" />
                  </CampoFormulario>
                  <CampoFormulario label="Tarea asignada de planeación">
                    <input type="text" value={planActual?.objetivo_planeacion ?? '—'}
                      disabled
                      className="campo-input disabled:bg-gray-50 disabled:text-gray-500" />
                  </CampoFormulario>
                  <CampoFormulario label="Novedad cumplimiento tratamiento">
                    <textarea value={tratamientoActual.novedad_cumplimiento_tratamiento ?? ''}
                      onChange={e => actualizarCampoHijo('tratamiento', 'novedad_cumplimiento_tratamiento', e.target.value, idxTratamiento)}
                      disabled={!esEditable('etapa_5') || tratamientoActual.tratamiento_completado}
                      rows={2}
                      className="campo-input resize-none disabled:bg-gray-50 disabled:text-gray-500" />
                  </CampoFormulario>
                  <CampoFormulario label="Tratamiento según planeación">
                    <SelectSiNo value={boolToStr(tratamientoActual.tratamiento_segun_planeacion)}
                      onChange={v => actualizarCampoHijo('tratamiento', 'tratamiento_segun_planeacion', strToBool(v), idxTratamiento)}
                      disabled={!esEditable('etapa_5') || tratamientoActual.tratamiento_completado} />
                  </CampoFormulario>
                  <CampoFormulario label="¿Actividades de tratamiento termico realizadas según planeación?">
                    <SelectSiNo value={boolToStr(tratamientoActual.tratamiento_completado)}
                      onChange={v => actualizarCampoHijo('tratamiento', 'tratamiento_completado', strToBool(v), idxTratamiento)}
                      disabled={!esEditable('etapa_5') || tratamientoActual.tratamiento_completado} />
                    <p className="text-xs text-amber-600 mt-1">
                      Importante: una vez marque Sí y guarde, no podrá realizar
                      modificaciones posteriores a este registro.
                    </p>
                  </CampoFormulario>
                </div>
              )}
            </FormEtapa>
          </div>
        )}

        {/* ── Etapa 7 — Despachos ──────────────────────────────────────────── */}
        {pestanaActiva === 'etapa6' && (
          <FormEtapa
            titulo="Etapa 7 — Despachos"
            editable={esEditable('etapa_6') && !datosDom.dom_liberado_cierre}
            guardando={guardando}
            onGuardar={() => guardarDom('Despacho guardado correctamente.', 'etapa_6')}
          >
            <div className="grid grid-cols-2 gap-4">
              <CampoFormulario label="Fecha entrega pactada">
                <input type="date" value={datosDom.fecha_entrega_pactada ?? ''}
                  onChange={e => actualizarCampoDom('fecha_entrega_pactada', e.target.value)}
                  disabled={!esEditable('etapa_6') || datosDom.dom_liberado_cierre}
                  className="campo-input disabled:bg-gray-50 disabled:text-gray-500" />
              </CampoFormulario>
              <CampoFormulario label="Fecha entrega planificada">
                <input type="date" value={datosDom.fecha_entrega_planificada ?? ''}
                  onChange={e => actualizarCampoDom('fecha_entrega_planificada', e.target.value)}
                  disabled={!esEditable('etapa_6') || datosDom.dom_liberado_cierre}
                  className="campo-input disabled:bg-gray-50 disabled:text-gray-500" />
              </CampoFormulario>
              <CampoFormulario label="Fecha entrega proyectada">
                <input type="date" value={datosDom.fecha_entrega_proyectada ?? ''}
                  onChange={e => actualizarCampoDom('fecha_entrega_proyectada', e.target.value)}
                  disabled={!esEditable('etapa_6') || datosDom.dom_liberado_cierre}
                  className="campo-input disabled:bg-gray-50 disabled:text-gray-500" />
              </CampoFormulario>
              <CampoFormulario label="Cantidad empaques">
                <input type="number" value={datosDom.cantidad_empaques ?? ''}
                  onChange={e => actualizarCampoDom('cantidad_empaques', e.target.value)}
                  disabled={!esEditable('etapa_6') || datosDom.dom_liberado_cierre}
                  className="campo-input disabled:bg-gray-50 disabled:text-gray-500" />
              </CampoFormulario>
              <CampoFormulario label="Empaque servicio">
                <select value={datosDom.empaque_servicio ?? ''}
                  onChange={e => actualizarCampoDom('empaque_servicio', e.target.value)}
                  disabled={!esEditable('etapa_6') || datosDom.dom_liberado_cierre}
                  className="campo-input disabled:bg-gray-50 disabled:text-gray-500">
                  <option value="">Seleccione una opción</option>
                  {empaques.map(e => (
                    <option key={e.lista_id} value={e.nombre}>{e.nombre}</option>
                  ))}
                </select>
              </CampoFormulario>
              <CampoFormulario label="Tipo negociación">
                <select value={datosDom.tipo_negociacion ?? ''}
                  onChange={e => actualizarCampoDom('tipo_negociacion', e.target.value)}
                  disabled={!esEditable('etapa_6') || datosDom.dom_liberado_cierre}
                  className="campo-input disabled:bg-gray-50 disabled:text-gray-500">
                  <option value="">Seleccione una opción</option>
                  {tiposNegociacion.map(t => (
                    <option key={t.lista_id} value={t.nombre}>{t.nombre}</option>
                  ))}
                </select>
              </CampoFormulario>
              <CampoFormulario label="Materiales externos">
                <input type="text" value={datosDom.materiales_externos ?? ''}
                  onChange={e => actualizarCampoDom('materiales_externos', e.target.value)}
                  disabled={!esEditable('etapa_6') || datosDom.dom_liberado_cierre}
                  className="campo-input disabled:bg-gray-50 disabled:text-gray-500" />
              </CampoFormulario>
              <CampoFormulario label="Vehículo">
                <input type="text" value={datosDom.vehiculo ?? ''}
                  onChange={e => actualizarCampoDom('vehiculo', e.target.value)}
                  disabled={!esEditable('etapa_6') || datosDom.dom_liberado_cierre}
                  className="campo-input disabled:bg-gray-50 disabled:text-gray-500" />
              </CampoFormulario>
              <CampoFormulario label="Orden entrega">
                <input type="text" value={datosDom.orden_entrega ?? ''}
                  onChange={e => actualizarCampoDom('orden_entrega', e.target.value)}
                  disabled={!esEditable('etapa_6') || datosDom.dom_liberado_cierre}
                  className="campo-input disabled:bg-gray-50 disabled:text-gray-500" />
              </CampoFormulario>
              <CampoFormulario label="¿Notas o comentarios del encargado de servicios externos?">
                <textarea value={datosDom.notas ?? ''}
                  onChange={e => actualizarCampoDom('notas', e.target.value)}
                  disabled={!esEditable('etapa_6') || datosDom.dom_liberado_cierre}
                  rows={2}
                  className="campo-input resize-none disabled:bg-gray-50 disabled:text-gray-500" />
              </CampoFormulario>
              <CampoFormulario label="Novedades cumplimiento">
                <textarea value={datosDom.novedades_cumplimiento ?? ''}
                  onChange={e => actualizarCampoDom('novedades_cumplimiento', e.target.value)}
                  disabled={!esEditable('etapa_6') || datosDom.dom_liberado_cierre}
                  rows={2}
                  className="campo-input resize-none disabled:bg-gray-50 disabled:text-gray-500" />
              </CampoFormulario>
              <CampoFormulario label="DOM entregado OK">
                <SelectSiNo value={boolToStr(datosDom.dom_entregado_ok)}
                  onChange={v => actualizarCampoDom('dom_entregado_ok', strToBool(v))}
                  disabled={!esEditable('etapa_6') || datosDom.dom_liberado_cierre} />
              </CampoFormulario>
              <CampoFormulario label="DOM liberado cierre">
                <SelectSiNo value={boolToStr(datosDom.dom_liberado_cierre)}
                  onChange={v => actualizarCampoDom('dom_liberado_cierre', strToBool(v))}
                  disabled={!esEditable('etapa_6') || datosDom.dom_liberado_cierre} />
                <p className="text-xs text-amber-600 mt-1">
                  Importante: una vez marque Sí y guarde, el DOM quedará
                  cerrado definitivamente.
                </p>
              </CampoFormulario>
            </div>
          </FormEtapa>
        )}

      </div>

      {/* Botón volver */}
      <div className="mt-6">
        <button onClick={() => navegar('/doms')}
          className="px-6 py-2 border border-gray-300 text-gray-600 text-sm
                     font-medium rounded hover:bg-gray-50">
          VOLVER
        </button>
      </div>

    </div>
  )
}

// ── Componentes auxiliares ─────────────────────────────────────────────────────

// Selector de registro hijo con botón para crear nuevo
function SelectorRegistro({ registros, idxActivo, onCambiar, etiqueta,
                             campoCierre, ultimoCerrado, puedeCrear, onNuevo, guardando }) {
  return (
    <div className="flex items-center gap-3 pb-3 border-b border-gray-100">
      <span className="text-sm text-gray-600">{etiqueta}:</span>
      {registros.map((r, i) => (
        <button key={r.id} onClick={() => onCambiar(i)}
          className={`px-3 py-1 text-sm rounded border
            ${idxActivo === i
              ? 'bg-[#1A56A0] text-white border-[#1A56A0]'
              : r[campoCierre]
                ? 'border-gray-200 text-gray-400 bg-gray-50'
                : 'border-gray-300 text-gray-600 hover:bg-gray-50'
            }`}>
          #{i + 1} {r[campoCierre] ? '✓' : ''}
        </button>
      ))}
      {puedeCrear && (
        <button
          onClick={onNuevo}
          disabled={(registros.length > 0 && !ultimoCerrado) || guardando}
          className="flex items-center gap-1 px-3 py-1 text-sm rounded border
                     border-dashed border-gray-300 text-gray-500
                     hover:border-[#1A56A0] hover:text-[#1A56A0]
                     disabled:opacity-40 disabled:cursor-not-allowed">
          <FiPlus size={13} /> Nuevo
        </button>
      )}
    </div>
  )
}

// Envuelve el contenido de cada etapa con título, badge y botón guardar
function FormEtapa({ titulo, editable, guardando, onGuardar, sinRegistro, children }) {
  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide">
          {titulo}
        </h2>
        {!editable && (
          <span className="text-xs px-2 py-1 bg-amber-50 text-amber-700
                           border border-amber-200 rounded">
            Solo lectura
          </span>
        )}
      </div>
      {sinRegistro ? (
        <p className="text-sm text-gray-400 text-center py-8">
          No hay registros disponibles para esta etapa en este DOM.
        </p>
      ) : (
        <>
          {children}
          {editable && (
            <div className="pt-4">
              <button onClick={onGuardar} disabled={guardando}
                className="px-6 py-2 bg-[#1A56A0] text-white text-sm font-medium
                           rounded hover:bg-[#134080] disabled:opacity-60
                           disabled:cursor-not-allowed">
                {guardando ? 'Guardando...' : 'ACTUALIZAR REGISTRO DOM'}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}

// Dropdown reutilizable para campos booleanos Sí/No
function SelectSiNo({ value, onChange, disabled }) {
  return (
    <select value={value} onChange={e => onChange(e.target.value)}
      disabled={disabled}
      className="campo-input disabled:bg-gray-50 disabled:text-gray-500">
      {OPCIONES_SI_NO.map(o => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  )
}

// Campo de solo lectura con nota informativa
function CampoLectura({ label, valor, nota }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-medium text-gray-600 uppercase tracking-wide">
        {label}
      </label>
      <div className="campo-input bg-gray-50 text-gray-500 cursor-not-allowed">
        {valor ?? '—'}
      </div>
      {nota && <p className="text-xs text-gray-400">{nota}</p>}
    </div>
  )
}

// Campo del consolidado con label y valor
function CampoConsolidado({ label, valor }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
        {label}
      </span>
      <span className="text-sm text-gray-800 border-b border-gray-100 pb-1">
        {valor ?? '—'}
      </span>
    </div>
  )
}

// Sección del consolidado con título
function SeccionConsolidado({ titulo, children }) {
  return (
    <div>
      <h3 className="text-xs font-semibold text-[#1A56A0] uppercase tracking-wide mb-3">
        {titulo}
      </h3>
      <div className="grid grid-cols-2 gap-4">
        {children}
      </div>
    </div>
  )
}

export default PaginaEditarDom