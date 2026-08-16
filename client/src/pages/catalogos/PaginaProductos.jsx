// src/pages/catalogos/PaginaProductos.jsx
import { useState, useEffect, useCallback } from 'react'
import { FiPlus, FiEdit2, FiXCircle } from 'react-icons/fi'
import { obtenerProductos, crearProducto, actualizarProducto, desactivarProducto, obtenerFamilias } from '../../api/catalogos'
import { toInt } from '../../utils/formatters'
import { useDebounce } from '../../hooks/useDebounce'
import { useEsEscritorio } from '../../hooks/useEsEscritorio'
import CampoFormulario from '../../components/common/CampoFormulario'
import AvisoSuelo from '../../components/common/AvisoSuelo'
import { extraerMensajeError } from '../../utils/errores'
import Toast from '../../components/common/Toast'
import ModalBase from '../../components/common/ModalBase'
import Par from '../../components/common/Par'
import Paginacion from '../../components/common/Paginacion'

const FORMULARIO_VACIO = { nombre_producto: '', familia_producto: '', tiempo_produccion_unitario: '' }

function PaginaProductos() {
  const [productos, setProductos] = useState([])
  const [familias, setFamilias]   = useState([])
  const [cargando, setCargando]   = useState(true)
  const [error, setError]         = useState(null)

  // Filtros
  const [busqueda, setBusqueda] = useState('')
  const textoDebounced = useDebounce(busqueda, 300)

  // Paginación en cliente — 20 filas por página en escritorio, 10 en móvil
  const esEscritorio = useEsEscritorio()
  const POR_PAGINA = esEscritorio ? 20 : 10
  const [pagina, setPagina] = useState(1)

  // Formulario
  const [productoEditando, setProductoEditando]   = useState(null)
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

  // Carga el listado de productos según el filtro de búsqueda
  const cargarProductos = useCallback(async () => {
    setCargando(true)
    setError(null)
    try {
      const filtros = { activo: true }
      if (textoDebounced) filtros.nombre = textoDebounced
      const r = await obtenerProductos(filtros)
      setProductos(r.data.productos)
    } catch {
      setError('Error al cargar los productos.')
    } finally {
      setCargando(false)
    }
  }, [textoDebounced])

  useEffect(() => {
    cargarProductos()
  }, [cargarProductos])

  // Al cambiar la búsqueda, vuelve a la primera página
  useEffect(() => { setPagina(1) }, [textoDebounced])

  // Corrige la página si quedó fuera de rango: menos resultados tras filtrar, o
  // cambio de breakpoint escritorio↔móvil (que cambia POR_PAGINA y totalPaginas)
  const totalPaginas = Math.max(1, Math.ceil(productos.length / POR_PAGINA))
  useEffect(() => {
    if (pagina > totalPaginas) setPagina(totalPaginas)
  }, [pagina, totalPaginas])

  // Pedazo de la lista visible en la página actual (lo usan tabla y tarjetas)
  const productosPagina = productos.slice((pagina - 1) * POR_PAGINA, pagina * POR_PAGINA)

  // Carga las familias de producto para el select del formulario
  useEffect(() => {
    obtenerFamilias({ activo: true })
      .then(r => setFamilias(r.data.familias))
      .catch(err => setError(extraerMensajeError(err, 'Error al cargar las familias de producto.')))
  }, [])

  // Abre el formulario vacío para crear un nuevo producto
  const abrirFormularioNuevo = () => {
    setProductoEditando(null)
    setFormulario(FORMULARIO_VACIO)
    setMostrarFormulario(true)
  }

  // Abre el formulario precargado con los datos del producto a editar
  const abrirFormularioEditar = (producto) => {
    setProductoEditando(producto)
    setFormulario({
      nombre_producto: producto.nombre_producto,
      familia_producto: producto.familia_detalle?.familia_id ?? '',
      tiempo_produccion_unitario: producto.tiempo_produccion_unitario ?? '',
    })
    setMostrarFormulario(true)
  }

  // Cierra el formulario y limpia su estado
  const cancelarFormulario = () => {
    setMostrarFormulario(false)
    setProductoEditando(null)
    setFormulario(FORMULARIO_VACIO)
  }

  // Guarda el producto — crea o actualiza según productoEditando
  const guardarProducto = async () => {
    setGuardando(true)
    setError(null)
    try {
      const datos = {
        nombre_producto: formulario.nombre_producto,
        familia_producto: toInt(formulario.familia_producto),
        tiempo_produccion_unitario: toInt(formulario.tiempo_produccion_unitario),
      }
      const esEdicion = Boolean(productoEditando)
      if (esEdicion) {
        await actualizarProducto(productoEditando.producto_id, datos)
      } else {
        await crearProducto(datos)
      }
      await cargarProductos()
      cancelarFormulario()
      mostrarExito(esEdicion ? 'Producto actualizado exitosamente' : 'Producto creado exitosamente')
    } catch {
      setError('Error al guardar el producto.')
    } finally {
      setGuardando(false)
    }
  }

  // Desactiva un producto previa confirmación
  const manejarDesactivar = async (producto) => {
    if (!await pedirConfirmacion('¿Está seguro que desea desactivar este producto?')) return
    setError(null)
    try {
      await desactivarProducto(producto.producto_id)
      await cargarProductos()
      mostrarExito('Producto desactivado exitosamente')
    } catch {
      setError('Error al desactivar el producto.')
    }
  }

  const formularioValido =
    formulario.nombre_producto.trim() !== '' &&
    formulario.familia_producto !== '' &&
    Number(formulario.tiempo_produccion_unitario) > 0

  return (
    <div className="space-y-4">

      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-800">
          Productos <span className="text-sm font-normal text-gray-400">({productos.length})</span>
        </h1>
        <button
          onClick={abrirFormularioNuevo}
          className="flex items-center gap-2 px-3 py-2 text-sm rounded bg-[#1A56A0] text-white hover:bg-[#164685]">
          <FiPlus size={16} /> Nuevo producto
        </button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {/* Formulario inline */}
      {mostrarFormulario && (
        <div className="bg-white rounded-lg border-2 border-[#1A56A0] p-4 space-y-4">
          <h2 className="text-sm font-medium text-gray-700">
            {productoEditando ? 'Editar producto' : 'Nuevo producto'}
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <CampoFormulario label="Nombre producto" obligatorio>
              <input
                type="text"
                value={formulario.nombre_producto}
                onChange={e => setFormulario(prev => ({ ...prev, nombre_producto: e.target.value }))}
                className="campo-input" />
            </CampoFormulario>
            <CampoFormulario label="Familia" obligatorio>
              <select
                value={formulario.familia_producto}
                onChange={e => setFormulario(prev => ({ ...prev, familia_producto: e.target.value }))}
                className="campo-input">
                <option value="">Seleccione una opción</option>
                {familias.map(familia => (
                  <option key={familia.familia_id} value={familia.familia_id}>
                    {familia.nombre_familia}
                  </option>
                ))}
              </select>
            </CampoFormulario>
            <CampoFormulario label="Tiempo unit. (min)" obligatorio>
              <input
                type="number"
                min="1"
                value={formulario.tiempo_produccion_unitario}
                onChange={e => setFormulario(prev => ({ ...prev, tiempo_produccion_unitario: e.target.value }))}
                className="campo-input" />
              <AvisoSuelo valor={formulario.tiempo_produccion_unitario} minimo={1} />
            </CampoFormulario>
          </div>
          <div className="flex gap-2">
            <button
              onClick={guardarProducto}
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

      {/* Filtro */}
      <div className="flex gap-3">
        <input
          type="text"
          placeholder="Buscar por nombre..."
          value={busqueda}
          onChange={e => setBusqueda(e.target.value)}
          className="campo-input flex-1" />
      </div>

      {/* Paginación superior */}
      {!cargando && productos.length > 0 && (
        <Paginacion pagina={pagina} totalPaginas={totalPaginas} total={productos.length} onPagina={setPagina} />
      )}

      {/* Tabla (escritorio) */}
      <div className="hidden md:block bg-white rounded-lg border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-[#1A56A0] text-white">
              <th className="text-left px-4 py-2 text-xs font-medium">Nombre producto</th>
              <th className="text-left px-4 py-2 text-xs font-medium">Familia</th>
              <th className="text-left px-4 py-2 text-xs font-medium">Tiempo unit. (min)</th>
              <th className="text-left px-4 py-2 text-xs font-medium">Estado</th>
              <th className="px-4 py-2 text-xs font-medium">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {cargando ? (
              <tr>
                <td colSpan={5} className="text-center py-8 text-gray-400 text-sm">Cargando...</td>
              </tr>
            ) : productos.length === 0 ? (
              <tr>
                <td colSpan={5} className="text-center py-8 text-gray-400 text-sm">Sin registros</td>
              </tr>
            ) : (
              productosPagina.map((producto, i) => (
                <tr key={producto.producto_id}
                  className={`border-t border-gray-100
                    ${producto.activo ? '' : 'opacity-50'}
                    ${i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}`}>
                  <td className="px-4 py-2 text-gray-700">{producto.nombre_producto}</td>
                  <td className="px-4 py-2 text-gray-700">{producto.familia_detalle?.nombre_familia ?? '—'}</td>
                  <td className="px-4 py-2 text-gray-700">{producto.tiempo_produccion_unitario}</td>
                  <td className="px-4 py-2">
                    <span className={`px-2 py-1 text-xs rounded-full font-medium
                      ${producto.activo ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'}`}>
                      {producto.activo ? 'Activo' : 'Inactivo'}
                    </span>
                  </td>
                  <td className="px-4 py-2">
                    <div className="flex items-center justify-center gap-2">
                      <button onClick={() => abrirFormularioEditar(producto)}
                        className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-medium rounded-full border border-blue-100 bg-blue-50 text-blue-700 hover:bg-blue-100">
                        <FiEdit2 size={14} />
                        Editar
                      </button>
                      {producto.activo && (
                        <button onClick={() => manejarDesactivar(producto)}
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
        ) : productos.length === 0 ? (
          <div className="bg-white rounded-lg border border-gray-200 py-8 text-center text-gray-400 text-sm">Sin registros</div>
        ) : (
          productosPagina.map((producto) => (
            <div key={producto.producto_id}
              className={`bg-white rounded-lg border border-gray-200 p-4 ${producto.activo ? '' : 'opacity-50'}`}>
              <Par etiqueta="Nombre producto">{producto.nombre_producto}</Par>
              <Par etiqueta="Familia">{producto.familia_detalle?.nombre_familia ?? '—'}</Par>
              <Par etiqueta="Tiempo unit. (min)">{producto.tiempo_produccion_unitario}</Par>
              <Par etiqueta="Estado">
                <span className={`px-2 py-1 text-xs rounded-full font-medium
                  ${producto.activo ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'}`}>
                  {producto.activo ? 'Activo' : 'Inactivo'}
                </span>
              </Par>
              <div className="flex gap-2 mt-3 pt-3 border-t border-gray-100">
                <button onClick={() => abrirFormularioEditar(producto)}
                  className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-medium rounded-lg border border-blue-100 bg-blue-50 text-blue-700 hover:bg-blue-100">
                  <FiEdit2 size={14} />
                  Editar
                </button>
                {producto.activo && (
                  <button onClick={() => manejarDesactivar(producto)}
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
      {!cargando && productos.length > 0 && (
        <Paginacion pagina={pagina} totalPaginas={totalPaginas} total={productos.length} onPagina={setPagina} />
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

export default PaginaProductos
