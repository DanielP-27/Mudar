// src/pages/catalogos/PaginaClientes.jsx
import { useState, useEffect, useCallback } from 'react'
import { FiPlus, FiEdit2, FiXCircle } from 'react-icons/fi'
import { obtenerClientes, crearCliente, actualizarCliente, desactivarCliente } from '../../api/catalogos'
import { useDebounce } from '../../hooks/useDebounce'
import { useEsEscritorio } from '../../hooks/useEsEscritorio'
import CampoFormulario from '../../components/common/CampoFormulario'
import Toast from '../../components/common/Toast'
import ModalBase from '../../components/common/ModalBase'
import Par from '../../components/common/Par'
import Paginacion from '../../components/common/Paginacion'

const FORMULARIO_VACIO = { nombre_cliente: '', nit: '' }

function PaginaClientes() {
  const [clientes, setClientes]   = useState([])
  const [cargando, setCargando]   = useState(true)
  const [error, setError]         = useState(null)

  // Filtros
  const [busqueda, setBusqueda]       = useState('')
  const [filtroActivo, setFiltroActivo] = useState('')
  const textoDebounced = useDebounce(busqueda, 300)

  // Paginación en cliente — 20 filas por página en escritorio, 10 en móvil
  const esEscritorio = useEsEscritorio()
  const POR_PAGINA = esEscritorio ? 20 : 10
  const [pagina, setPagina] = useState(1)

  // Formulario
  const [clienteEditando, setClienteEditando]     = useState(null)
  const [mostrarFormulario, setMostrarFormulario] = useState(false)
  const [formulario, setFormulario]               = useState(FORMULARIO_VACIO)
  const [guardando, setGuardando]                 = useState(false)

  // Toast de éxito (no bloqueante) — auto-cierra a los 5s
  const [exito, setExito] = useState(null)
  const mostrarExito = (msg) => {
    setExito(msg)
    setTimeout(() => setExito(null), 5000)
  }

  // Confirmación de desactivación — modal propio en vez de window.confirm()
  const [confirmacion, setConfirmacion] = useState(null) // { mensaje, resolve } | null
  const pedirConfirmacion = (mensaje) =>
    new Promise(resolve => setConfirmacion({ mensaje, resolve }))

  // Carga el listado de clientes según filtros activos
  const cargarClientes = useCallback(async () => {
    setCargando(true)
    setError(null)
    try {
      const filtros = { activo: filtroActivo || true }
      if (textoDebounced) filtros.nombre = textoDebounced
      const r = await obtenerClientes(filtros)
      setClientes(r.data.clientes)
    } catch {
      setError('Error al cargar los clientes.')
    } finally {
      setCargando(false)
    }
  }, [textoDebounced, filtroActivo])

  useEffect(() => {
    cargarClientes()
  }, [cargarClientes])

  // Al cambiar búsqueda o filtro, vuelve a la primera página
  useEffect(() => { setPagina(1) }, [textoDebounced, filtroActivo])

  // Corrige la página si quedó fuera de rango: menos resultados tras filtrar, o
  // cambio de breakpoint escritorio↔móvil (que cambia POR_PAGINA y totalPaginas)
  const totalPaginas = Math.max(1, Math.ceil(clientes.length / POR_PAGINA))
  useEffect(() => {
    if (pagina > totalPaginas) setPagina(totalPaginas)
  }, [pagina, totalPaginas])

  // Pedazo de la lista visible en la página actual (lo usan tabla y tarjetas)
  const clientesPagina = clientes.slice((pagina - 1) * POR_PAGINA, pagina * POR_PAGINA)

  // Abre el formulario vacío para crear un nuevo cliente
  const abrirFormularioNuevo = () => {
    setClienteEditando(null)
    setFormulario(FORMULARIO_VACIO)
    setMostrarFormulario(true)
  }

  // Abre el formulario precargado con los datos del cliente a editar
  const abrirFormularioEditar = (cliente) => {
    setClienteEditando(cliente)
    setFormulario({ nombre_cliente: cliente.nombre_cliente, nit: cliente.nit ?? '' })
    setMostrarFormulario(true)
  }

  // Cierra el formulario y limpia su estado
  const cancelarFormulario = () => {
    setMostrarFormulario(false)
    setClienteEditando(null)
    setFormulario(FORMULARIO_VACIO)
  }

  // Guarda el cliente — crea o actualiza según clienteEditando
  const guardarCliente = async () => {
    setGuardando(true)
    setError(null)
    try {
      const esEdicion = Boolean(clienteEditando)
      if (esEdicion) {
        await actualizarCliente(clienteEditando.cliente_id, formulario)
      } else {
        await crearCliente(formulario)
      }
      await cargarClientes()
      cancelarFormulario()
      mostrarExito(esEdicion ? 'Cliente actualizado exitosamente' : 'Cliente creado exitosamente')
    } catch {
      setError('Error al guardar el cliente.')
    } finally {
      setGuardando(false)
    }
  }

  // Desactiva un cliente previa confirmación
  const manejarDesactivar = async (cliente) => {
    if (!await pedirConfirmacion('¿Está seguro que desea desactivar este cliente?')) return
    setError(null)
    try {
      await desactivarCliente(cliente.cliente_id)
      await cargarClientes()
      mostrarExito('Cliente desactivado exitosamente')
    } catch {
      setError('Error al desactivar el cliente.')
    }
  }

  const formularioValido = formulario.nombre_cliente.trim() !== '' && formulario.nit.trim() !== ''

  return (
    <div className="space-y-4">

      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-800">
          Clientes <span className="text-sm font-normal text-gray-400">({clientes.length})</span>
        </h1>
        <button
          onClick={abrirFormularioNuevo}
          className="flex items-center gap-2 px-3 py-2 text-sm rounded bg-[#1A56A0] text-white hover:bg-[#164685]">
          <FiPlus size={16} /> Nuevo cliente
        </button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {/* Formulario inline */}
      {mostrarFormulario && (
        <div className="bg-white rounded-lg border-2 border-[#1A56A0] p-4 space-y-4">
          <h2 className="text-sm font-medium text-gray-700">
            {clienteEditando ? 'Editar cliente' : 'Nuevo cliente'}
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <CampoFormulario label="Nombre cliente" obligatorio>
              <input
                type="text"
                value={formulario.nombre_cliente}
                onChange={e => setFormulario(prev => ({ ...prev, nombre_cliente: e.target.value }))}
                className="campo-input" />
            </CampoFormulario>
            <CampoFormulario label="NIT" obligatorio>
              <input
                type="text"
                value={formulario.nit}
                onChange={e => setFormulario(prev => ({ ...prev, nit: e.target.value }))}
                className="campo-input" />
            </CampoFormulario>
          </div>
          <div className="flex gap-2">
            <button
              onClick={guardarCliente}
              disabled={!formularioValido || guardando}
              className="px-4 py-2 text-sm rounded bg-[#1A56A0] text-white hover:bg-[#164685] disabled:opacity-50">
              {guardando ? 'Guardando...' : 'Guardar'}
            </button>
            <button
              onClick={cancelarFormulario}
              disabled={guardando}
              className="px-4 py-2 text-sm rounded border border-gray-300 text-gray-600 hover:bg-gray-50">
              Cancelar
            </button>
          </div>
        </div>
      )}

      {/* Filtros */}
      <div className="flex gap-3">
        <input
          type="text"
          placeholder="Buscar por nombre..."
          value={busqueda}
          onChange={e => setBusqueda(e.target.value)}
          className="campo-input flex-1" />
        <select
          value={filtroActivo}
          onChange={e => setFiltroActivo(e.target.value)}
          className="campo-input w-40">
          <option value="">Todos</option>
          <option value="true">Activos</option>
          <option value="false">Inactivos</option>
        </select>
      </div>

      {/* Paginación superior */}
      {!cargando && clientes.length > 0 && (
        <Paginacion pagina={pagina} totalPaginas={totalPaginas} total={clientes.length} onPagina={setPagina} />
      )}

      {/* Tabla (escritorio) */}
      <div className="hidden md:block bg-white rounded-lg border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-[#1A56A0] text-white">
              <th className="text-left px-4 py-2 text-xs font-medium">NIT</th>
              <th className="text-left px-4 py-2 text-xs font-medium">Nombre cliente</th>
              <th className="text-left px-4 py-2 text-xs font-medium">Estado</th>
              <th className="px-4 py-2 text-xs font-medium">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {cargando ? (
              <tr>
                <td colSpan={4} className="text-center py-8 text-gray-400 text-sm">Cargando...</td>
              </tr>
            ) : clientes.length === 0 ? (
              <tr>
                <td colSpan={4} className="text-center py-8 text-gray-400 text-sm">Sin registros</td>
              </tr>
            ) : (
              clientesPagina.map((cliente, i) => (
                <tr key={cliente.cliente_id}
                  className={`border-t border-gray-100
                    ${cliente.activo ? '' : 'opacity-50'}
                    ${i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}`}>
                  <td className="px-4 py-2 text-gray-700">{cliente.nit ?? '—'}</td>
                  <td className="px-4 py-2 text-gray-700">{cliente.nombre_cliente}</td>
                  <td className="px-4 py-2">
                    <span className={`px-2 py-1 text-xs rounded-full font-medium
                      ${cliente.activo ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'}`}>
                      {cliente.activo ? 'Activo' : 'Inactivo'}
                    </span>
                  </td>
                  <td className="px-4 py-2">
                    <div className="flex items-center justify-center gap-2">
                      <button onClick={() => abrirFormularioEditar(cliente)}
                        className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-medium rounded-full border border-blue-100 bg-blue-50 text-blue-700 hover:bg-blue-100">
                        <FiEdit2 size={14} />
                        Editar
                      </button>
                      {cliente.activo && (
                        <button onClick={() => manejarDesactivar(cliente)}
                          className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-medium rounded-full border border-red-100 bg-red-50 text-red-700 hover:bg-red-100">
                          <FiXCircle size={14} />
                          Desactivar
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Tarjetas (móvil) */}
      <div className="md:hidden space-y-3">
        {cargando ? (
          <div className="bg-white rounded-lg border border-gray-200 py-8 text-center text-gray-400 text-sm">Cargando...</div>
        ) : clientes.length === 0 ? (
          <div className="bg-white rounded-lg border border-gray-200 py-8 text-center text-gray-400 text-sm">Sin registros</div>
        ) : (
          clientesPagina.map((cliente) => (
            <div key={cliente.cliente_id}
              className={`bg-white rounded-lg border border-gray-200 p-4 ${cliente.activo ? '' : 'opacity-50'}`}>
              <Par etiqueta="NIT">{cliente.nit ?? '—'}</Par>
              <Par etiqueta="Nombre cliente">{cliente.nombre_cliente}</Par>
              <Par etiqueta="Estado">
                <span className={`px-2 py-1 text-xs rounded-full font-medium
                  ${cliente.activo ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'}`}>
                  {cliente.activo ? 'Activo' : 'Inactivo'}
                </span>
              </Par>
              <div className="flex gap-2 mt-3 pt-3 border-t border-gray-100">
                <button onClick={() => abrirFormularioEditar(cliente)}
                  className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-medium rounded-lg border border-blue-100 bg-blue-50 text-blue-700 hover:bg-blue-100">
                  <FiEdit2 size={14} />
                  Editar
                </button>
                {cliente.activo && (
                  <button onClick={() => manejarDesactivar(cliente)}
                    className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-medium rounded-lg border border-red-100 bg-red-50 text-red-700 hover:bg-red-100">
                    <FiXCircle size={14} />
                    Desactivar
                  </button>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Paginación inferior */}
      {!cargando && clientes.length > 0 && (
        <Paginacion pagina={pagina} totalPaginas={totalPaginas} total={clientes.length} onPagina={setPagina} />
      )}

      <Toast mensaje={exito} />

      <ModalBase
        abierto={!!confirmacion}
        variante="confirmacion"
        titulo="Confirmar desactivación"
        mensaje={confirmacion?.mensaje}
        onCerrar={() => { confirmacion?.resolve(false); setConfirmacion(null) }}
        acciones={[
          { texto: 'Cancelar',   estilo: 'peligro',  onClick: () => { confirmacion?.resolve(false); setConfirmacion(null) } },
          { texto: 'Desactivar', estilo: 'primario', onClick: () => { confirmacion?.resolve(true);  setConfirmacion(null) } },
        ]}
      />
    </div>
  )
}

export default PaginaClientes
