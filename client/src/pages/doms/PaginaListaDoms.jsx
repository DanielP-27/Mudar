// src/pages/doms/PaginaListaDoms.jsx
import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { FiSearch, FiEdit2, FiEye, FiChevronLeft, FiChevronRight } from 'react-icons/fi'
import { useAutenticacion } from '../../context/AuthContext'
import { obtenerDoms } from '../../api/doms'
import { obtenerClientes, obtenerListasPorTipo } from '../../api/catalogos'
import { useDebounce } from '../../hooks/useDebounce'
import { ROLES } from '../../routes/RoleRoute'
import TypeaheadInput from '../../components/common/TypeaheadInput'

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

  // Paginación
  const [paginaActual, setPaginaActual]   = useState(1)
  const [totalPaginas, setTotalPaginas]   = useState(1)
  const [totalRegistros, setTotalRegistros] = useState(0)
  const PAGE_SIZE = 20

  // Filtros
  const [filtroEstado, setFiltroEstado]         = useState('')
  const [filtroResponsable, setFiltroResponsable] = useState('')
  const [filtroFechaInicio, setFiltroFechaInicio] = useState('')
  const [filtroFechaFin, setFiltroFechaFin]       = useState('')

  // Typeahead cliente
  const [busquedaCliente, setBusquedaCliente]           = useState('')
  const [sugerenciasCliente, setSugerenciasCliente]     = useState([])
  const [mostrarSugerencias, setMostrarSugerencias]     = useState(false)
  const [clienteSeleccionado, setClienteSeleccionado]   = useState(null)
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
    }).catch(() => setError('Error al cargar los filtros.'))
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
      if (filtroEstado)        filtros.estado   = filtroEstado
      if (filtroResponsable)   filtros.responsable = filtroResponsable
      if (filtroFechaInicio)   filtros.fecha_inicio = filtroFechaInicio
      if (filtroFechaFin)      filtros.fecha_fin    = filtroFechaFin

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
  }, [clienteSeleccionado, filtroEstado, filtroResponsable, filtroFechaInicio, filtroFechaFin])

  // Carga inicial y cuando cambian los filtros
  useEffect(() => {
    cargarDoms(1)
  }, [cargarDoms])

  // Limpia todos los filtros
  const limpiarFiltros = () => {
    setBusquedaCliente('')
    setClienteSeleccionado(null)
    setFiltroEstado('')
    setFiltroResponsable('')
    setFiltroFechaInicio('')
    setFiltroFechaFin('')
  }

  // Determina si un DOM está vencido
  const estaVencido = (dom) => {
    if (!dom.fecha_entrega_pactada) return false
    return new Date(dom.fecha_entrega_pactada) < new Date()
  }

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
      <div className="bg-white rounded-lg border border-gray-200 p-4 mb-4">
        <div className="grid grid-cols-2 gap-3 mb-3">

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

        </div>

        {/* Botón limpiar filtros */}
        <button onClick={limpiarFiltros}
          className="text-sm text-gray-500 hover:text-gray-700 underline">
          Limpiar filtros
        </button>
      </div>

      {/* Error */}
      {error && <p className="text-sm text-red-600 mb-4">{error}</p>}

      {/* Tabla */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
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

                    {/* Fecha entrega */}
                    <td className={`px-4 py-3 text-sm
                      ${vencido ? 'text-red-600 font-medium' : 'text-gray-600'}`}>
                      {dom.fecha_entrega_pactada
                        ? new Date(dom.fecha_entrega_pactada).toLocaleDateString('es-CO')
                        : '—'}
                    </td>

                    {/* Estado vencimiento */}
                    <td className="px-4 py-3">
                      {vencido ? (
                        <span className="px-2 py-1 text-xs rounded-full bg-red-100 text-red-700 font-medium">
                          Vencido
                        </span>
                      ) : dom.fecha_entrega_pactada &&
                        (new Date(dom.fecha_entrega_pactada) - new Date()) / (1000 * 60 * 60 * 24) <= 7 ? (
                        <span className="px-2 py-1 text-xs rounded-full bg-amber-100 text-amber-700">
                          Vence pronto
                        </span>
                      ) : (
                        <span className="px-2 py-1 text-xs rounded-full bg-green-100 text-green-700">
                          Vigente
                        </span>
                      )}
                    </td>

                    {/* Acciones */}
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-center gap-2">
                        <button
                          onClick={() => navegar(`/doms/${dom.dom_id}`)}
                          className="p-1.5 text-gray-500 hover:text-[#1A56A0] hover:bg-blue-50 rounded"
                          title="Ver DOM">
                          <FiEye size={15} />
                        </button>
                        {puedeEditar && (
                          <button
                            onClick={() => navegar(`/doms/${dom.dom_id}/editar`)}
                            className="p-1.5 text-gray-500 hover:text-[#1A56A0] hover:bg-blue-50 rounded"
                            title="Editar DOM">
                            <FiEdit2 size={15} />
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

        {/* Paginación */}
        {!cargando && doms.length > 0 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200">
            <span className="text-xs text-gray-500">
              Página {paginaActual} de {totalPaginas} — {totalRegistros} registros
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => cargarDoms(paginaActual - 1)}
                disabled={paginaActual === 1}
                className="p-1.5 rounded border border-gray-300 text-gray-600
                           hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed">
                <FiChevronLeft size={15} />
              </button>
              <button
                onClick={() => cargarDoms(paginaActual + 1)}
                disabled={paginaActual === totalPaginas}
                className="p-1.5 rounded border border-gray-300 text-gray-600
                           hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed">
                <FiChevronRight size={15} />
              </button>
            </div>
          </div>
        )}
      </div>

    </div>
  )
}

export default PaginaListaDoms