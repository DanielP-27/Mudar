// src/pages/doms/PaginaListaDoms.jsx
import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { FiSearch, FiEdit2, FiEye, FiRotateCcw, FiChevronDown, FiChevronUp } from 'react-icons/fi'
import { useAutenticacion } from '../../context/AuthContext'
import { obtenerDoms } from '../../api/doms'
import { obtenerClientes, obtenerListasPorTipo } from '../../api/catalogos'
import { useDebounce } from '../../hooks/useDebounce'
import { useEsEscritorio } from '../../hooks/useEsEscritorio'
import { ROLES } from '../../routes/RoleRoute'
import TypeaheadInput from '../../components/common/TypeaheadInput'
import Par from '../../components/common/Par'
import Paginacion from '../../components/common/Paginacion'
import { extraerMensajeError } from '../../utils/errores'
import { formatearFecha } from '../../utils/formatters'

// Roles que pueden editar DOMs
const ROLES_EDITAR = [
  ROLES.ADMIN, ROLES.ANALISTA_1, ROLES.ANALISTA_2,
  ROLES.PLANEADOR, ROLES.LIDER_PLANTA
]

function PaginaListaDoms() {
  const navegar         = useNavigate()
  const { usuario }     = useAutenticacion()

  // Datos de la tabla
  const [doms, setDoms]           = useState([])
  const [cargando, setCargando]   = useState(true)
  const [error, setError]         = useState(null)

  // Paginación (server-side) — 20 por página en escritorio, 10 en móvil
  const esEscritorio = useEsEscritorio()
  const [paginaActual, setPaginaActual]   = useState(1)
  const [totalPaginas, setTotalPaginas]   = useState(1)
  const [totalRegistros, setTotalRegistros] = useState(0)
  const PAGE_SIZE = esEscritorio ? 20 : 10

  // Filtros
  const [filtroNumeroDom, setFiltroNumeroDom]   = useState('')
  const [filtroEstado, setFiltroEstado]         = useState('')
  const [filtroResponsable, setFiltroResponsable] = useState('')
  const [filtroFechaInicio, setFiltroFechaInicio] = useState('')
  const [filtroFechaFin, setFiltroFechaFin]       = useState('')

  // Ordenamiento (Opción B: campo+dirección en un valor "campo:direccion")
  const [ordenamiento, setOrdenamiento] = useState('fecha_entrega:asc')

  // Filtro por fecha de planeación (fecha exacta, no rango)
  const [filtroFechaPlaneacion, setFiltroFechaPlaneacion] = useState('')

  // Panel de filtros plegable (solo móvil; en escritorio siempre visible vía md:block)
  const [filtrosAbiertos, setFiltrosAbiertos] = useState(false)

  // Versión debounced del número de DOM (evita una petición por cada dígito)
  const numeroDomDebounced = useDebounce(filtroNumeroDom, 300)

  // Typeahead cliente
  const [busquedaCliente, setBusquedaCliente]           = useState('')
  const [sugerenciasCliente, setSugerenciasCliente]     = useState([])
  const [mostrarSugerencias, setMostrarSugerencias]     = useState(false)
  const [clienteSeleccionado, setClienteSeleccionado]   = useState(null)

  // Nº de filtros activos (para el contador del panel plegado; el rango de fechas cuenta como 1)
  const filtrosActivos = [
    filtroNumeroDom, clienteSeleccionado, filtroEstado, filtroResponsable,
    filtroFechaInicio || filtroFechaFin, filtroFechaPlaneacion,
  ].filter(Boolean).length
  const textoCliente = useDebounce(busquedaCliente, 300)

  // Opciones de dropdowns
  const [tiposEstado, setTiposEstado]     = useState([])
  const [responsables, setResponsables]   = useState([])

  // Carga opciones de dropdowns al montar
  useEffect(() => {
    Promise.all([
      obtenerListasPorTipo('TIPO_ESTADO_DOM'),
      obtenerListasPorTipo('RESPONSABLE'),
    ]).then(([rTipos, rResp]) => {
      setTiposEstado(rTipos.data.listas)
      setResponsables(rResp.data.listas)
    }).catch(err => setError(extraerMensajeError(err, 'Error al cargar los filtros.')))
  }, [])

  // Typeahead cliente
  useEffect(() => {
    if (textoCliente.length < 2) return setSugerenciasCliente([])
    obtenerClientes({ nombre: textoCliente, activo: true })
      .then(r => setSugerenciasCliente(r.data.clientes ?? []))
      .catch(() => setSugerenciasCliente([]))
  }, [textoCliente])

  // Carga DOMs — se ejecuta al cambiar filtros o página
  const cargarDoms = useCallback(async (pagina = 1) => {
    setCargando(true)
    setError(null)
    try {
      const filtros = {
        page:      pagina,
        page_size: PAGE_SIZE,
        dom_liberado_cierre: false,
      }
      if (clienteSeleccionado) filtros.cliente  = clienteSeleccionado.cliente_id
      if (numeroDomDebounced)  filtros.numero_dom = numeroDomDebounced
      if (filtroEstado)        filtros.estado   = filtroEstado
      if (filtroResponsable)   filtros.responsable = filtroResponsable
      if (filtroFechaInicio)   filtros.fecha_inicio = filtroFechaInicio
      if (filtroFechaFin)      filtros.fecha_fin    = filtroFechaFin
      if (filtroFechaPlaneacion) filtros.fecha_planeacion = filtroFechaPlaneacion

      const [orden, direccion] = ordenamiento.split(':')
      filtros.orden = orden
      filtros.direccion = direccion

      const res = await obtenerDoms(filtros)
      setDoms(res.data.doms)
      setTotalPaginas(res.data.total_pages)
      setTotalRegistros(res.data.total)
      setPaginaActual(pagina)
    } catch {
      setError('Error al cargar los registros DOM.')
    } finally {
      setCargando(false)
    }
  }, [clienteSeleccionado, numeroDomDebounced, filtroEstado, filtroResponsable, filtroFechaInicio, filtroFechaFin, filtroFechaPlaneacion, ordenamiento, PAGE_SIZE])

  // Carga inicial y cuando cambian los filtros
  useEffect(() => {
    cargarDoms(1)
  }, [cargarDoms])

  // Limpia todos los filtros
  const limpiarFiltros = () => {
    setBusquedaCliente('')
    setClienteSeleccionado(null)
    setFiltroNumeroDom('')
    setFiltroEstado('')
    setFiltroResponsable('')
    setFiltroFechaInicio('')
    setFiltroFechaFin('')
    setFiltroFechaPlaneacion('')
    setOrdenamiento('fecha_entrega:asc')
  }

  // Vencimiento clasificado por el backend (nivel_urgencia): 0 vencido · 1 próximo · 2 activo.
  // Ya no se recalcula con fechas en JS — el backend es la única fuente de verdad
  // (mismo criterio que el orden y el dashboard; evita bugs de zona horaria).
  const estaVencido = (dom) => dom.nivel_urgencia === 0

  // Determina si el usuario puede editar DOMs
  const puedeEditar = ROLES_EDITAR.includes(usuario?.rol)

  return (
    <div className="max-w-7xl mx-auto">

      {/* Encabezado */}
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-gray-800">Registros DOM</h1>
        <p className="text-sm text-gray-500 mt-1">
          {totalRegistros} registro{totalRegistros !== 1 ? 's' : ''} encontrado{totalRegistros !== 1 ? 's' : ''}
        </p>
      </div>

      {/* Filtros */}
      <div className="bg-white rounded-lg border border-gray-200 mb-4 overflow-hidden">
        {/* Encabezado del panel */}
        <button type="button" onClick={() => setFiltrosAbiertos(v => !v)}
          className="w-full bg-[#1A56A0] px-4 py-2.5 flex items-center gap-2 text-left md:cursor-default">
          <h2 className="text-sm font-semibold text-white uppercase tracking-wide">
            Filtros de búsqueda{filtrosActivos > 0 && ` (${filtrosActivos})`}
          </h2>
          <span className="ml-auto text-white md:hidden">
            {filtrosAbiertos ? <FiChevronUp size={18} /> : <FiChevronDown size={18} />}
          </span>
        </button>
        {/* Cuerpo */}
        <div className={`p-4 ${filtrosAbiertos ? '' : 'hidden'} md:block`}>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">

          {/* Número de DOM */}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-gray-600 uppercase tracking-wide">
              No. DOM
            </label>
            <input type="number" min="1"
              value={filtroNumeroDom}
              onChange={e => setFiltroNumeroDom(e.target.value)}
              placeholder="Ej. 75"
              className="campo-input" />
          </div>

          {/* Typeahead cliente */}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-gray-600 uppercase tracking-wide">
              Cliente
            </label>
            <TypeaheadInput
              valor={busquedaCliente}
              onChange={e => {
                setBusquedaCliente(e.target.value)
                setMostrarSugerencias(true)
                setClienteSeleccionado(null)
              }}
              sugerencias={sugerenciasCliente}
              mostrar={mostrarSugerencias}
              onSeleccionar={c => {
                setClienteSeleccionado(c)
                setBusquedaCliente(c.nombre_cliente)
                setMostrarSugerencias(false)
              }}
              obtenerLabel={c => c.nombre_cliente}
              obtenerKey={c => c.cliente_id}
              placeholder="Buscar por cliente..."
            />
          </div>

          {/* Estado */}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-gray-600 uppercase tracking-wide">
              Tipo o estado DOM
            </label>
            <select value={filtroEstado}
              onChange={e => setFiltroEstado(e.target.value)}
              className="campo-input">
              <option value="">Todos</option>
              {tiposEstado.map(t => (
                <option key={t.lista_id} value={t.nombre}>{t.nombre}</option>
              ))}
            </select>
          </div>

          {/* Responsable */}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-gray-600 uppercase tracking-wide">
              Responsable
            </label>
            <select value={filtroResponsable}
              onChange={e => setFiltroResponsable(e.target.value)}
              className="campo-input">
              <option value="">Todos</option>
              {responsables.map(r => (
                <option key={r.lista_id} value={r.nombre}>{r.nombre}</option>
              ))}
            </select>
          </div>

          {/* Rango de fechas */}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-gray-600 uppercase tracking-wide">
              Rango fecha entrega
            </label>
            <div className="flex gap-2">
              <input type="date"
                value={filtroFechaInicio}
                onChange={e => setFiltroFechaInicio(e.target.value)}
                className="campo-input flex-1" />
              <input type="date"
                value={filtroFechaFin}
                onChange={e => setFiltroFechaFin(e.target.value)}
                className="campo-input flex-1" />
            </div>
          </div>

          {/* Fecha de planeación (fecha exacta) */}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-gray-600 uppercase tracking-wide">
              Fecha de planeación
            </label>
            <input type="date"
              value={filtroFechaPlaneacion}
              onChange={e => setFiltroFechaPlaneacion(e.target.value)}
              className="campo-input" />
          </div>

          {/* Ordenar por — misma fila que Fecha de planeación */}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-gray-600 uppercase tracking-wide">
              Ordenar por
            </label>
            <select value={ordenamiento}
              onChange={e => setOrdenamiento(e.target.value)}
              className="campo-input">
              <option value="fecha_entrega:asc">Fecha de entrega (más próxima primero)</option>
              <option value="fecha_entrega:desc">Fecha de entrega (más lejana primero)</option>
              <option value="cliente:asc">Cliente (A → Z)</option>
              <option value="cliente:desc">Cliente (Z → A)</option>
              <option value="dom:asc">N.º DOM (ascendente)</option>
              <option value="dom:desc">N.º DOM (descendente)</option>
            </select>
          </div>

        </div>

        {/* Botón limpiar filtros — outline/secundario, no compite con acciones primarias */}
        <button onClick={limpiarFiltros}
          className="inline-flex items-center gap-1.5 px-3 py-1 text-sm font-medium rounded-full border border-gray-300 text-gray-600 hover:text-[#1A56A0] hover:border-[#1A56A0]">
          <FiRotateCcw size={14} />
          Limpiar filtros
        </button>
        </div>
      </div>

      {/* Error */}
      {error && <p className="text-sm text-red-600 mb-4">{error}</p>}

      {/* Paginación superior */}
      {!cargando && doms.length > 0 && (
        <div className="mb-4">
          <Paginacion pagina={paginaActual} totalPaginas={totalPaginas} total={totalRegistros} onPagina={cargarDoms} />
        </div>
      )}

      {/* Tabla (escritorio) */}
      <div className="hidden md:block bg-white rounded-lg border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-[#1A56A0] text-white">
              <th className="text-left px-4 py-3 text-xs font-medium">DOM</th>
              <th className="text-left px-4 py-3 text-xs font-medium">Cliente</th>
              <th className="text-left px-4 py-3 text-xs font-medium">Responsable</th>
              <th className="text-left px-4 py-3 text-xs font-medium">Estado</th>
              <th className="text-left px-4 py-3 text-xs font-medium">Fecha entrega</th>
              <th className="text-left px-4 py-3 text-xs font-medium">Vencimiento</th>
              <th className="px-4 py-3 text-xs font-medium">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {cargando ? (
              <tr>
                <td colSpan={7} className="text-center py-12 text-gray-400 text-sm">
                  Cargando registros...
                </td>
              </tr>
            ) : doms.length === 0 ? (
              <tr>
                <td colSpan={7} className="text-center py-12 text-gray-400 text-sm">
                  No se encontraron registros DOM con los filtros seleccionados.
                </td>
              </tr>
            ) : (
              doms.map((dom, i) => {
                const vencido = estaVencido(dom)
                return (
                  <tr key={dom.dom_id}
                    className={`border-t border-gray-100
                      ${vencido ? 'bg-red-50' : i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}
                      hover:bg-blue-50 transition-colors`}>

                    {/* Número DOM */}
                    <td className="px-4 py-3 font-medium text-[#1A56A0]">
                      #{dom.dom_id}
                    </td>

                    {/* Cliente */}
                    <td className="px-4 py-3 text-gray-700">
                      {dom.nombre_cliente_detalle}
                    </td>

                    {/* Responsable */}
                    <td className="px-4 py-3 text-gray-600">
                      {dom.responsable}
                    </td>

                    {/* Estado */}
                    <td className="px-4 py-3">
                      <span className="px-2 py-1 text-xs rounded-full bg-blue-50 text-blue-700">
                        {dom.tipo_estado_dom}
                      </span>
                    </td>

                    {/* Fecha entrega — fecha efectiva (proyectada, o solicitada si no hay) */}
                    <td className={`px-4 py-3 text-sm
                      ${vencido ? 'text-red-600 font-medium' : 'text-gray-600'}`}>
                      {formatearFecha(dom.fecha_criterio)}
                    </td>

                    {/* Estado vencimiento — clasificación del backend (nivel_urgencia) */}
                    <td className="px-4 py-3">
                      {vencido ? (
                        <span className="px-2 py-1 text-xs rounded-full bg-red-100 text-red-700 font-medium">
                          Vencido
                        </span>
                      ) : dom.nivel_urgencia === 1 ? (
                        <span className="px-2 py-1 text-xs rounded-full bg-amber-100 text-amber-700">
                          Vence pronto
                        </span>
                      ) : (
                        <span className="px-2 py-1 text-xs rounded-full bg-green-100 text-green-700">
                          Activo
                        </span>
                      )}
                    </td>

                    {/* Acciones */}
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-center gap-2">
                        <button
                          onClick={() => navegar(`/doms/${dom.dom_id}`)}
                          className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-medium rounded-full border border-violet-100 bg-violet-50 text-violet-700 hover:bg-violet-100">
                          <FiEye size={14} />
                          Ver
                        </button>
                        {puedeEditar && (
                          <button
                            onClick={() => navegar(`/doms/${dom.dom_id}/editar`)}
                            className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-medium rounded-full border border-blue-100 bg-blue-50 text-blue-700 hover:bg-blue-100">
                            <FiEdit2 size={14} />
                            Editar
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Tarjetas (móvil) */}
      <div className="md:hidden space-y-3">
        {cargando ? (
          <div className="bg-white rounded-lg border border-gray-200 py-8 text-center text-gray-400 text-sm">Cargando registros...</div>
        ) : doms.length === 0 ? (
          <div className="bg-white rounded-lg border border-gray-200 py-8 text-center text-gray-400 text-sm">No se encontraron registros DOM con los filtros seleccionados.</div>
        ) : (
          doms.map((dom) => {
            const vencido = estaVencido(dom)
            return (
              <div key={dom.dom_id}
                className={`rounded-lg border p-4 ${vencido ? 'bg-red-50 border-red-200' : 'bg-white border-gray-200'}`}>
                <Par etiqueta="DOM"><span className="font-medium text-[#1A56A0]">#{dom.dom_id}</span></Par>
                <Par etiqueta="Cliente">{dom.nombre_cliente_detalle}</Par>
                <Par etiqueta="Responsable">{dom.responsable}</Par>
                <Par etiqueta="Estado">
                  <span className="px-2 py-1 text-xs rounded-full bg-blue-50 text-blue-700">
                    {dom.tipo_estado_dom}
                  </span>
                </Par>
                <Par etiqueta="Fecha entrega">
                  <span className={vencido ? 'text-red-600 font-medium' : ''}>
                    {formatearFecha(dom.fecha_criterio)}
                  </span>
                </Par>
                <Par etiqueta="Vencimiento">
                  {vencido ? (
                    <span className="px-2 py-1 text-xs rounded-full bg-red-100 text-red-700 font-medium">Vencido</span>
                  ) : dom.nivel_urgencia === 1 ? (
                    <span className="px-2 py-1 text-xs rounded-full bg-amber-100 text-amber-700">Vence pronto</span>
                  ) : (
                    <span className="px-2 py-1 text-xs rounded-full bg-green-100 text-green-700">Activo</span>
                  )}
                </Par>
                <div className="flex gap-2 mt-3 pt-3 border-t border-gray-100">
                  <button
                    onClick={() => navegar(`/doms/${dom.dom_id}`)}
                    className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-medium rounded-lg border border-violet-100 bg-violet-50 text-violet-700 hover:bg-violet-100">
                    <FiEye size={14} />
                    Ver
                  </button>
                  {puedeEditar && (
                    <button
                      onClick={() => navegar(`/doms/${dom.dom_id}/editar`)}
                      className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-medium rounded-lg border border-blue-100 bg-blue-50 text-blue-700 hover:bg-blue-100">
                      <FiEdit2 size={14} />
                      Editar
                    </button>
                  )}
                </div>
              </div>
            )
          })
        )}
      </div>

      {/* Paginación inferior */}
      {!cargando && doms.length > 0 && (
        <div className="mt-4">
          <Paginacion pagina={paginaActual} totalPaginas={totalPaginas} total={totalRegistros} onPagina={cargarDoms} />
        </div>
      )}

    </div>
  )
}

export default PaginaListaDoms