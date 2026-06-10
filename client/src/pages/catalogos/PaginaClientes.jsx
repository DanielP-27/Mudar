// src/pages/catalogos/PaginaClientes.jsx
import { useState, useEffect, useCallback } from 'react'
import { FiPlus, FiEdit2, FiXCircle } from 'react-icons/fi'
import { obtenerClientes, crearCliente, actualizarCliente, desactivarCliente } from '../../api/catalogos'
import { useDebounce } from '../../hooks/useDebounce'
import CampoFormulario from '../../components/common/CampoFormulario'

const FORMULARIO_VACIO = { nombre_cliente: '', nit: '' }

function PaginaClientes() {
  const [clientes, setClientes]   = useState([])
  const [cargando, setCargando]   = useState(true)
  const [error, setError]         = useState(null)

  // Filtros
  const [busqueda, setBusqueda]       = useState('')
  const [filtroActivo, setFiltroActivo] = useState('')
  const textoDebounced = useDebounce(busqueda, 300)

  // Formulario
  const [clienteEditando, setClienteEditando]     = useState(null)
  const [mostrarFormulario, setMostrarFormulario] = useState(false)
  const [formulario, setFormulario]               = useState(FORMULARIO_VACIO)
  const [guardando, setGuardando]                 = useState(false)

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
      if (clienteEditando) {
        await actualizarCliente(clienteEditando.cliente_id, formulario)
      } else {
        await crearCliente(formulario)
      }
      await cargarClientes()
      cancelarFormulario()
    } catch {
      setError('Error al guardar el cliente.')
    } finally {
      setGuardando(false)
    }
  }

  // Desactiva un cliente previa confirmación
  const manejarDesactivar = async (cliente) => {
    if (!window.confirm('¿Desactivar este cliente?')) return
    setError(null)
    try {
      await desactivarCliente(cliente.cliente_id)
      await cargarClientes()
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

      {/* Tabla */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
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
              clientes.map((cliente, i) => (
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
                        className="text-[#1A56A0] hover:text-[#164685]" title="Editar">
                        <FiEdit2 size={16} />
                      </button>
                      {cliente.activo && (
                        <button onClick={() => manejarDesactivar(cliente)}
                          className="text-red-500 hover:text-red-700" title="Desactivar">
                          <FiXCircle size={16} />
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
    </div>
  )
}

export default PaginaClientes
