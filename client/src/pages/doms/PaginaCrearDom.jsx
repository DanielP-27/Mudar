// src/pages/doms/PaginaCrearDom.jsx
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { FiEye, FiFileText, FiBriefcase, FiPlus, FiTrash2 } from 'react-icons/fi'
import { crearDom } from '../../api/doms'
import { obtenerClientes, obtenerProductos, obtenerListasPorTipo } from '../../api/catalogos'
import { useDebounce } from '../../hooks/useDebounce'
import { toInt } from '../../utils/formatters'
import TypeaheadInput from '../../components/common/TypeaheadInput'
import CampoFormulario from '../../components/common/CampoFormulario'

// Tipos de DOM que no llevan productos ni etapas de producción
const TIPOS_ADMINISTRATIVOS = ['ADP', 'Documentos']

// Estado inicial de etapa 0 — creación del DOM
const estadoInicialEtapa0 = {
  nombre_cliente:           '',
  descripcion:              '',
  tipo_estado_dom:          '',
  fecha_solicitada_cliente: '',
  responsable:              '',
}

// Estado inicial de etapa 1 — gestión comercial y diseño
const estadoInicialEtapa1 = {
  orden_compra:               '',
  tiempo_salida_almacen:      '',
  rentabilidad:               '',
  campana_venta:              '',
  numero_cotizacion:          '',
  numero_factura:             '',
  dom_relacionado_produccion: '',
}

function PaginaCrearDom() {
  const navegar = useNavigate()

  // Estado centralizado de ambas etapas
  const [datosEtapa0, setDatosEtapa0] = useState(estadoInicialEtapa0)
  const [datosEtapa1, setDatosEtapa1] = useState(estadoInicialEtapa1)

  // Pestaña activa — inicia en etapa 0
  const [pestanaActiva, setPestanaActiva] = useState('etapa0')

  // Estado de carga y error del formulario
  const [guardando, setGuardando] = useState(false)
  const [error, setError]         = useState(null)

  // Opciones para los dropdowns
  const [tiposEstadoDom, setTiposEstadoDom] = useState([])
  const [responsables, setResponsables]     = useState([])
  const [cargandoListas, setCargandoListas] = useState(true)

  // Typeahead cliente
  const [busquedaCliente, setBusquedaCliente]       = useState('')
  const [sugerenciasCliente, setSugerenciasCliente] = useState([])
  const [mostrarSugerenciasCliente, setMostrarSugerenciasCliente] = useState(false)
  const textoCliente = useDebounce(busquedaCliente, 300)

  // Typeahead producto
  const [busquedaProducto, setBusquedaProducto]       = useState('')
  const [sugerenciasProducto, setSugerenciasProducto] = useState([])
  const [mostrarSugerenciasProducto, setMostrarSugerenciasProducto] = useState(false)
  const [cantidadProducto, setCantidadProducto]       = useState('')
  const [productoSeleccionado, setProductoSeleccionado] = useState(null)
  const textoProducto = useDebounce(busquedaProducto, 300)

  // Lista de productos agregados al DOM
  const [productosAgregados, setProductosAgregados] = useState([])

  // Determina si el tipo de DOM seleccionado es administrativo
  const esDomAdministrativo = TIPOS_ADMINISTRATIVOS.includes(datosEtapa0.tipo_estado_dom)

  // Carga los dropdowns al montar la página
  useEffect(() => {
    const cargarListas = async () => {
      try {
        const [resTipos, resResponsables] = await Promise.all([
          obtenerListasPorTipo('TIPO_ESTADO_DOM'),
          obtenerListasPorTipo('RESPONSABLE'),
        ])
        setTiposEstadoDom(resTipos.data.listas)
        setResponsables(resResponsables.data.listas)
      } catch {
        setError('Error al cargar los datos del formulario.')
      } finally {
        setCargandoListas(false)
      }
    }
    cargarListas()
  }, [])

  // Typeahead cliente — busca cuando el texto debounced cambia
  useEffect(() => {
    if (textoCliente.length < 2) return setSugerenciasCliente([])
    obtenerClientes({ nombre: textoCliente, activo: true })
      .then(r => setSugerenciasCliente(r.data.clientes ?? []))
      .catch(() => setSugerenciasCliente([]))
  }, [textoCliente])

  // Typeahead producto — busca cuando el texto debounced cambia
  useEffect(() => {
    if (textoProducto.length < 2) return setSugerenciasProducto([])
    obtenerProductos({ nombre: textoProducto, activo: true })
      .then(r => setSugerenciasProducto(r.data.productos ?? []))
      .catch(() => setSugerenciasProducto([]))
  }, [textoProducto])

  // Actualiza un campo específico de etapa 0
  const actualizarEtapa0 = (campo, valor) =>
    setDatosEtapa0(prev => ({ ...prev, [campo]: valor }))

  // Actualiza un campo específico de etapa 1
  const actualizarEtapa1 = (campo, valor) =>
    setDatosEtapa1(prev => ({ ...prev, [campo]: valor }))

  // Agrega un producto a la lista — valida que tenga producto y cantidad
  const agregarProducto = () => {
    if (!productoSeleccionado || !cantidadProducto) return
    const yaExiste = productosAgregados.find(
      p => p.tipo_producto === productoSeleccionado.producto_id
    )
    if (yaExiste) {
      setError('Este producto ya fue agregado.')
      return
    }
    setProductosAgregados(prev => [...prev, {
      tipo_producto:   productoSeleccionado.producto_id,
      nombre_producto: productoSeleccionado.nombre_producto,
      cantidad_pedido: toInt(cantidadProducto),
    }])
    // Limpiar campos de producto después de agregar
    setBusquedaProducto('')
    setCantidadProducto('')
    setProductoSeleccionado(null)
    setError(null)
  }

  // Elimina un producto de la lista por su índice
  const eliminarProducto = (idx) =>
    setProductosAgregados(prev => prev.filter((_, i) => i !== idx))

  // Envía el formulario al backend
  const manejarCrear = async () => {
    // Validar producto obligatorio para DOMs productivos
    if (!esDomAdministrativo && productosAgregados.length === 0) {
      setError('Debe agregar al menos un producto antes de crear el registro DOM.')
      return
    }
    setGuardando(true)
    setError(null)
    try {
      const payload = {
        ...datosEtapa0,
        ...(!esDomAdministrativo ? datosEtapa1 : {}),
        nombre_cliente:        toInt(datosEtapa0.nombre_cliente),
        tiempo_salida_almacen: toInt(datosEtapa1.tiempo_salida_almacen),
        rentabilidad:          toInt(datosEtapa1.rentabilidad),
        numero_factura:        toInt(datosEtapa1.numero_factura),
        campana_venta:         datosEtapa1.campana_venta === 'true',
        dom_relacionado_produccion: datosEtapa1.dom_relacionado_produccion === 'true',
        // Productos — array vacío para DOMs administrativos
        productos: esDomAdministrativo
          ? []
          : productosAgregados.map(p => ({
              tipo_producto:   p.tipo_producto,
              cantidad_pedido: p.cantidad_pedido,
            })),
      }
      const res = await crearDom(payload)
      navegar(`/doms/${res.data.dom.dom_id}/editar`)
    } catch (err) {
      setError(
        err.response?.data?.error
          ?? err.response?.data?.detail
          ?? 'Error al crear el registro DOM. Verifique los campos obligatorios.'
      )
    } finally {
      setGuardando(false)
    }
  }

  // Pestañas del formulario — solo para DOMs productivos
  const pestanas = [
    { id: 'consolidado', icono: <FiEye size={15} />,       label: 'Ver consolidado' },
    { id: 'etapa0',      icono: <FiFileText size={15} />,  label: 'Etapa 1 — Creación del DOM' },
    { id: 'etapa1',      icono: <FiBriefcase size={15} />, label: 'Etapa 2 — Gestión comercial' },
  ]

  if (cargandoListas) return (
    <div className="flex items-center justify-center h-64 text-gray-500 text-sm">
      Cargando formulario...
    </div>
  )

  return (
    <div className="max-w-4xl mx-auto">

      {/* Encabezado */}
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-gray-800">Crear nuevo registro DOM</h1>
        <p className="text-sm text-gray-500 mt-1">
          {esDomAdministrativo
            ? 'DOM administrativo — complete la información del trámite.'
            : 'Solo se encuentran habilitadas las etapas 1 y 2. Los campos marcados con'
          }
          {!esDomAdministrativo && (
            <span className="text-red-500 font-medium"> *</span>
          )}
          {!esDomAdministrativo && ' son obligatorios.'}
        </p>
      </div>

      {/* ── Formulario administrativo ADP/Documentos ────────── */}
      {esDomAdministrativo ? (
        <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-5">
          <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-4">
            Información del trámite
          </h2>

          {/* Campos automáticos */}
          <div className="grid grid-cols-2 gap-4">
            <CampoLectura label="Fecha asignación DOM"
              valor={new Date().toLocaleDateString('es-CO')}
              nota="Se genera automáticamente" />
            <CampoLectura label="Número DOM"
              valor="El número de registro DOM es asignado automaticamente por el sistema al guardar el registro"
              nota="Se asigna al guardar" />
          </div>

          {/* Tipo DOM */}
          <CampoFormulario label="Tipo o estado DOM" obligatorio>
            <select value={datosEtapa0.tipo_estado_dom}
              onChange={e => actualizarEtapa0('tipo_estado_dom', e.target.value)}
              className="campo-input">
              <option value="">Seleccione una opción</option>
              {tiposEstadoDom.map(t => (
                <option key={t.lista_id} value={t.nombre}>{t.nombre}</option>
              ))}
            </select>
          </CampoFormulario>

          {/* Cliente — typeahead */}
          <CampoFormulario label="Nombre del cliente" obligatorio>
            <TypeaheadInput
              valor={busquedaCliente}
              onChange={e => {
                setBusquedaCliente(e.target.value)
                setMostrarSugerenciasCliente(true)
                actualizarEtapa0('nombre_cliente', '')
              }}
              sugerencias={sugerenciasCliente}
              mostrar={mostrarSugerenciasCliente}
              onSeleccionar={c => {
                actualizarEtapa0('nombre_cliente', c.cliente_id)
                setBusquedaCliente(c.nombre_cliente)
                setMostrarSugerenciasCliente(false)
              }}
              obtenerLabel={c => c.nombre_cliente}
              obtenerKey={c => c.cliente_id}
              placeholder="Digite el nombre del cliente"
            />
          </CampoFormulario>

          {/* Descripción del trámite */}
          <CampoFormulario label="Descripción del trámite">
            <textarea value={datosEtapa0.descripcion}
              onChange={e => actualizarEtapa0('descripcion', e.target.value)}
              rows={3}
              placeholder="Describa el trámite o procedimiento interno"
              className="campo-input resize-none" />
          </CampoFormulario>

          {/* Fecha límite respuesta */}
          <CampoFormulario label="Fecha límite respuesta" obligatorio>
            <input type="date"
              value={datosEtapa0.fecha_solicitada_cliente}
              onChange={e => actualizarEtapa0('fecha_solicitada_cliente', e.target.value)}
              className="campo-input" />
          </CampoFormulario>

          {/* Responsable */}
          <CampoFormulario label="Responsable" obligatorio>
            <select value={datosEtapa0.responsable}
              onChange={e => actualizarEtapa0('responsable', e.target.value)}
              className="campo-input">
              <option value="">Seleccione una opción</option>
              {responsables.map(r => (
                <option key={r.lista_id} value={r.nombre}>{r.nombre}</option>
              ))}
            </select>
          </CampoFormulario>
        </div>

      ) : (

        /* ── Formulario productivo con pestañas ─────────────── */
        <>
          {/* Sistema de pestañas */}
          <div className="border-b border-gray-200 mb-6">
            <div className="flex gap-0">
              {pestanas.map(p => (
                <button key={p.id}
                  onClick={() => setPestanaActiva(p.id)}
                  className={`
                    flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2
                    transition-colors
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

          <div className="bg-white rounded-lg border border-gray-200 p-6">

            {/* Pestaña: Ver consolidado */}
            {pestanaActiva === 'consolidado' && (
              <div className="space-y-4">
                <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-4">
                  Información consolidada
                </h2>
                <div className="grid grid-cols-2 gap-4">
                  <CampoConsolidado label="Cliente"              valor={busquedaCliente} />
                  <CampoConsolidado label="Tipo o estado DOM"    valor={datosEtapa0.tipo_estado_dom} />
                  <CampoConsolidado label="Fecha solicitada"     valor={datosEtapa0.fecha_solicitada_cliente} />
                  <CampoConsolidado label="Responsable"
                    valor={responsables.find(r => r.nombre === datosEtapa0.responsable)?.nombre} />
                  <CampoConsolidado label="Descripción"          valor={datosEtapa0.descripcion} />
                  <CampoConsolidado label="Orden de compra"      valor={datosEtapa1.orden_compra} />
                  <CampoConsolidado label="Número cotización"    valor={datosEtapa1.numero_cotizacion} />
                  <CampoConsolidado label="Número factura"       valor={datosEtapa1.numero_factura} />
                  <CampoConsolidado label="Rentabilidad (%)"     valor={datosEtapa1.rentabilidad} />
                  <CampoConsolidado label="Campaña de venta"
                    valor={datosEtapa1.campana_venta === 'true' ? 'Sí'
                         : datosEtapa1.campana_venta === 'false' ? 'No' : '—'} />
                </div>

                {/* Productos agregados en consolidado */}
                {productosAgregados.length > 0 && (
                  <div className="mt-4">
                    <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                      Productos
                    </h3>
                    <table className="w-full text-sm border border-gray-200 rounded">
                      <thead>
                        <tr className="bg-gray-50">
                          <th className="text-left px-3 py-2 text-xs font-medium text-gray-600">Producto</th>
                          <th className="text-left px-3 py-2 text-xs font-medium text-gray-600">Cantidad</th>
                        </tr>
                      </thead>
                      <tbody>
                        {productosAgregados.map((p, i) => (
                          <tr key={i} className="border-t border-gray-100">
                            <td className="px-3 py-2">{p.nombre_producto}</td>
                            <td className="px-3 py-2">{p.cantidad_pedido}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {/* Pestaña: Etapa 1 — Creación del DOM */}
            {pestanaActiva === 'etapa0' && (
              <div className="space-y-5">
                <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-4">
                  Etapa 1 — Creación del DOM
                </h2>

                {/* Campos automáticos */}
                <div className="grid grid-cols-2 gap-4">
                  <CampoLectura label="Fecha asignación DOM"
                    valor={new Date().toLocaleDateString('es-CO')}
                    nota="Se genera automáticamente" />
                  <CampoLectura label="Número DOM"
                    valor="Automático"
                    nota="Se asigna al guardar" />
                </div>

                {/* Cliente — typeahead */}
                <CampoFormulario label="Nombre del cliente" obligatorio>
                  <TypeaheadInput
                    valor={busquedaCliente}
                    onChange={e => {
                      setBusquedaCliente(e.target.value)
                      setMostrarSugerenciasCliente(true)
                      actualizarEtapa0('nombre_cliente', '')
                    }}
                    sugerencias={sugerenciasCliente}
                    mostrar={mostrarSugerenciasCliente}
                    onSeleccionar={c => {
                      actualizarEtapa0('nombre_cliente', c.cliente_id)
                      setBusquedaCliente(c.nombre_cliente)
                      setMostrarSugerenciasCliente(false)
                    }}
                    obtenerLabel={c => c.nombre_cliente}
                    obtenerKey={c => c.cliente_id}
                    placeholder="Digite el nombre del cliente"
                  />
                </CampoFormulario>

                {/* Descripción */}
                <CampoFormulario label="Descripción">
                  <textarea value={datosEtapa0.descripcion}
                    onChange={e => actualizarEtapa0('descripcion', e.target.value)}
                    rows={3}
                    placeholder="En caso de ser necesario, agregue información relevante respecto de este DOM"
                    className="campo-input resize-none" />
                </CampoFormulario>

                {/* Tipo estado DOM */}
                <CampoFormulario label="Tipo o estado DOM" obligatorio>
                  <select value={datosEtapa0.tipo_estado_dom}
                    onChange={e => actualizarEtapa0('tipo_estado_dom', e.target.value)}
                    className="campo-input">
                    <option value="">Seleccione una opción</option>
                    {tiposEstadoDom.map(t => (
                      <option key={t.lista_id} value={t.nombre}>{t.nombre}</option>
                    ))}
                  </select>
                </CampoFormulario>

                {/* Fecha solicitada cliente */}
                <CampoFormulario label="Fecha solicitada cliente" obligatorio>
                  <input type="date"
                    value={datosEtapa0.fecha_solicitada_cliente}
                    onChange={e => actualizarEtapa0('fecha_solicitada_cliente', e.target.value)}
                    className="campo-input" />
                </CampoFormulario>

                {/* Responsable */}
                <CampoFormulario label="Responsable" obligatorio>
                  <select value={datosEtapa0.responsable}
                    onChange={e => actualizarEtapa0('responsable', e.target.value)}
                    className="campo-input">
                    <option value="">Seleccione una opción</option>
                    {responsables.map(r => (
                      <option key={r.lista_id} value={r.nombre}>{r.nombre}</option>
                    ))}
                  </select>
                </CampoFormulario>

                {/* Bloque de productos */}
                <div className="border border-gray-200 rounded-lg p-4 space-y-3">
                  <h3 className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
                    Productos <span className="text-red-500">*</span>
                  </h3>

                  {/* Typeahead producto + cantidad */}
                  <div className="grid grid-cols-3 gap-3 items-end">
                    <div className="col-span-2">
                      <CampoFormulario label="Producto">
                        <TypeaheadInput
                          valor={busquedaProducto}
                          onChange={e => {
                            setBusquedaProducto(e.target.value)
                            setMostrarSugerenciasProducto(true)
                            setProductoSeleccionado(null)
                          }}
                          sugerencias={sugerenciasProducto}
                          mostrar={mostrarSugerenciasProducto}
                          onSeleccionar={p => {
                            setProductoSeleccionado(p)
                            setBusquedaProducto(p.nombre_producto)
                            setMostrarSugerenciasProducto(false)
                          }}
                          obtenerLabel={p => p.nombre_producto}
                          obtenerKey={p => p.producto_id}
                          placeholder="Digite el nombre del producto"
                        />
                      </CampoFormulario>
                    </div>
                    <CampoFormulario label="Cantidad">
                      <input type="number"
                        value={cantidadProducto}
                        onChange={e => setCantidadProducto(e.target.value)}
                        placeholder="Cantidad"
                        min="1"
                        className="campo-input" />
                    </CampoFormulario>
                  </div>

                  {/* Botón agregar */}
                  <button
                    onClick={agregarProducto}
                    disabled={!productoSeleccionado || !cantidadProducto}
                    className="flex items-center gap-2 px-4 py-2 text-sm font-medium
                               text-[#1A56A0] border border-[#1A56A0] rounded
                               hover:bg-blue-50 disabled:opacity-40 disabled:cursor-not-allowed">
                    <FiPlus size={14} /> Agregar producto
                  </button>

                  {/* Lista de productos agregados */}
                  {productosAgregados.length > 0 && (
                    <table className="w-full text-sm border border-gray-200 rounded mt-2">
                      <thead>
                        <tr className="bg-gray-50">
                          <th className="text-left px-3 py-2 text-xs font-medium text-gray-600">Producto</th>
                          <th className="text-left px-3 py-2 text-xs font-medium text-gray-600">Cantidad</th>
                          <th className="px-3 py-2"></th>
                        </tr>
                      </thead>
                      <tbody>
                        {productosAgregados.map((p, i) => (
                          <tr key={i} className="border-t border-gray-100">
                            <td className="px-3 py-2">{p.nombre_producto}</td>
                            <td className="px-3 py-2">{p.cantidad_pedido}</td>
                            <td className="px-3 py-2 text-right">
                              <button onClick={() => eliminarProducto(i)}
                                className="text-red-400 hover:text-red-600">
                                <FiTrash2 size={14} />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              </div>
            )}

            {/* Pestaña: Etapa 2 — Gestión comercial */}
            {pestanaActiva === 'etapa1' && (
              <div className="space-y-5">
                <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-4">
                  Etapa 2 — Gestión comercial y diseño
                </h2>
                <div className="grid grid-cols-2 gap-4">
                  <CampoFormulario label="Orden de compra">
                    <input type="text" value={datosEtapa1.orden_compra}
                      onChange={e => actualizarEtapa1('orden_compra', e.target.value)}
                      placeholder="Número orden de compra"
                      className="campo-input" />
                  </CampoFormulario>
                  <CampoFormulario label="Número cotización">
                    <input type="text" value={datosEtapa1.numero_cotizacion}
                      onChange={e => actualizarEtapa1('numero_cotizacion', e.target.value)}
                      placeholder="Número cotización"
                      className="campo-input" />
                  </CampoFormulario>
                  <CampoFormulario label="Número factura de venta Mudar de Colombia">
                    <input type="number" value={datosEtapa1.numero_factura}
                      onChange={e => actualizarEtapa1('numero_factura', e.target.value)}
                      placeholder="Número factura de venta"
                      className="campo-input" />
                  </CampoFormulario>
                  <CampoFormulario label="Rentabilidad (%)">
                    <input type="number" value={datosEtapa1.rentabilidad}
                      onChange={e => actualizarEtapa1('rentabilidad', e.target.value)}
                      placeholder="Porcentaje de rentabilidad"
                      className="campo-input" />
                  </CampoFormulario>
                  <CampoFormulario label="Tiempo salida almacén (minutos)">
                    <input type="number" value={datosEtapa1.tiempo_salida_almacen}
                      onChange={e => actualizarEtapa1('tiempo_salida_almacen', e.target.value)}
                      placeholder="Tiempo en minutos"
                      className="campo-input" />
                  </CampoFormulario>
                  <CampoFormulario label="¿DOM resultado de campaña de venta?">
                    <select value={datosEtapa1.campana_venta}
                      onChange={e => actualizarEtapa1('campana_venta', e.target.value)}
                      className="campo-input">
                      <option value="">Seleccione una opción</option>
                      <option value="false">No</option>
                      <option value="true">Sí</option>
                    </select>
                  </CampoFormulario>
                </div>

                <CampoFormulario label="¿DOM relacionado con producción?">
                  <select value={datosEtapa1.dom_relacionado_produccion}
                    onChange={e => actualizarEtapa1('dom_relacionado_produccion', e.target.value)}
                    className="campo-input">
                    <option value="">Seleccione una opción</option>
                    <option value="false">No</option>
                    <option value="true">Sí</option>
                  </select>
                  <p className="text-xs text-amber-600 mt-1">
                    Importante: una vez seleccione Sí y guarde, no podrá realizar
                    modificaciones posteriores a esta etapa.
                  </p>
                </CampoFormulario>
              </div>
            )}
          </div>
        </>
      )}

      {/* Mensaje de error */}
      {error && <p className="text-sm text-red-600 mt-4">{error}</p>}

      {/* Botones de acción */}
      <div className="flex gap-3 mt-6">
        <button onClick={manejarCrear} disabled={guardando}
          className="px-6 py-2 bg-[#1A56A0] text-white text-sm font-medium rounded
                     hover:bg-[#134080] disabled:opacity-60 disabled:cursor-not-allowed">
          {guardando ? 'Guardando...' : 'CREAR REGISTRO DOM'}
        </button>
        <button onClick={() => navegar('/dashboard')}
          className="px-6 py-2 border border-gray-300 text-gray-600 text-sm
                     font-medium rounded hover:bg-gray-50">
          VOLVER AL DASHBOARD
        </button>
      </div>

    </div>
  )
}

// ── Componentes auxiliares ─────────────────────────────────────────────────────

function CampoLectura({ label, valor, nota }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-medium text-gray-600 uppercase tracking-wide">
        {label}
      </label>
      <div className="campo-input bg-gray-50 text-gray-500 cursor-not-allowed">
        {valor}
      </div>
      {nota && <p className="text-xs text-gray-400">{nota}</p>}
    </div>
  )
}

function CampoConsolidado({ label, valor }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
        {label}
      </span>
      <span className="text-sm text-gray-800 border-b border-gray-100 pb-1">
        {valor || '—'}
      </span>
    </div>
  )
}

export default PaginaCrearDom