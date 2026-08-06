// src/pages/dashboard/PaginaDashboard.jsx
import { useState, useEffect } from 'react'
import { obtenerDashboard } from '../../api/dashboard'
import { extraerMensajeError } from '../../utils/errores'
import { formatearFecha } from '../../utils/formatters'

// Bloque de cumplimiento DESACTIVADO hasta después de la V1.0 (2026-08-05).
// Dos razones: los nulos cuentan como incumplimiento, y el consolidado suma dos
// denominadores distintos (planeaciones para almacén/producción/tratamiento, DOMs
// para despacho). Corregir el nulo no habría arreglado lo segundo.
// El backend sigue calculando y devolviendo los 5 campos: aquí solo se dejan de
// pintar. No se borra nada. Para reactivarlo, poner en true.
const MOSTRAR_CUMPLIMIENTO = false

// Colores de fondo/texto según el resultado de cumplimiento
const ESTILOS_CUMPLIMIENTO = {
  CUMPLIÓ:    'bg-green-100 text-green-700',
  NO_CUMPLIÓ: 'bg-red-100 text-red-700',
  PARCIAL:    'bg-yellow-100 text-yellow-700',
  SIN_DATOS:  'bg-gray-100 text-gray-600',
}

// Etiquetas legibles para cada fila de la tabla de cumplimiento
const FILAS_CUMPLIMIENTO = [
  { campo: 'cumplimiento_almacen',      etiqueta: 'Almacén' },
  { campo: 'cumplimiento_produccion',   etiqueta: 'Producción' },
  { campo: 'cumplimiento_tratamiento',  etiqueta: 'Tratamiento' },
  { campo: 'cumplimiento_despacho',     etiqueta: 'Despacho' },
  { campo: 'cumplimiento_consolidado',  etiqueta: 'Consolidado' },
]

function PaginaDashboard() {
  const [metricas, setMetricas] = useState(null)
  const [cargando, setCargando] = useState(true)
  const [error, setError]       = useState(null)

  // Carga las métricas del dashboard al montar
  useEffect(() => {
    obtenerDashboard()
      .then(r => setMetricas(r.data.dashboard))
      .catch(err => setError(extraerMensajeError(err, 'Error al cargar el dashboard.')))
      .finally(() => setCargando(false))
  }, [])

  if (cargando) {
    return <div className="text-center py-12 text-gray-400 text-sm">Cargando dashboard...</div>
  }

  if (error) {
    return <div className="text-center py-12 text-red-600 text-sm">{error}</div>
  }

  if (!metricas) {
    return null
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-gray-800">Dashboard</h1>

      {/* Consolidado DOMs activos — foco operativo (trabajo en curso) */}
      <div>
        <h2 className="text-sm font-medium text-gray-700 mb-3">Consolidado DOMs activos</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <TarjetaResumen label="DOMs activos"        valor={metricas.total_doms_activos} />
          <TarjetaResumen label="Cantidad pedida"     valor={metricas.cantidad_pedida_activos} />
          <TarjetaResumen label="Cantidad elaborada"  valor={metricas.cantidad_elaborada_activos} />
          <TarjetaResumen label="Cantidad pendiente"  valor={metricas.cantidad_pendiente_activos} />
        </div>
      </div>

      {/* Productos pendientes — backlog completo de DOMs activos */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <h2 className="px-4 py-3 text-sm font-medium text-gray-700 border-b border-gray-200">
          Productos pendientes — DOMs activos
        </h2>
        {metricas.productos_pendientes_activos.length === 0 ? (
          <p className="px-4 py-3 text-sm text-gray-400">Sin registros</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-[#1A56A0] text-white">
                <th className="text-left px-4 py-2 text-xs font-medium">Producto</th>
                <th className="text-left px-4 py-2 text-xs font-medium">Cant. pendiente</th>
                <th className="text-left px-4 py-2 text-xs font-medium">DOMs involucrados</th>
              </tr>
            </thead>
            <tbody>
              {metricas.productos_pendientes_activos.map((p, i) => (
                <tr key={p.nombre_producto} className={i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                  <td className="px-4 py-2 text-gray-700">{p.nombre_producto}</td>
                  <td className="px-4 py-2 text-gray-700">{p.cantidad_pendiente}</td>
                  <td className="px-4 py-2 text-gray-700">{p.doms_involucrados}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Consolidado histórico — referencia (todo el tiempo, incluidos cerrados) */}
      <div>
        <h2 className="text-sm font-medium text-gray-500 mb-3">Consolidado histórico</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <TarjetaResumen label="Total DOMs"          valor={metricas.total_doms} />
          <TarjetaResumen label="DOMs cerrados"       valor={metricas.total_doms_cerrados} />
          <TarjetaResumen label="DOMs abiertos"       valor={metricas.total_doms_activos} />
          <TarjetaResumen label="Unidades elaboradas" valor={metricas.unidades_elaboradas_historico} />
        </div>
      </div>

      {/* Bloque 2 — DOMs por etapa */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <h2 className="px-4 py-3 text-sm font-medium text-gray-700 border-b border-gray-200">
          DOMs por etapa
        </h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-[#1A56A0] text-white">
              <th className="text-left px-4 py-2 text-xs font-medium">Etapa</th>
              <th className="text-left px-4 py-2 text-xs font-medium">Total</th>
            </tr>
          </thead>
          <tbody>
            {metricas.doms_por_etapa.map((fila, i) => (
              <tr key={fila.etapa} className={i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                <td className="px-4 py-2 text-gray-700">{fila.etapa}</td>
                <td className="px-4 py-2 text-gray-700">{fila.total}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Bloque 3 — Alertas */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ListaAlertaDoms
          titulo="DOMs vencidos"
          doms={metricas.doms_vencidos}
          colorTexto="text-red-600"
          colorFondo="bg-red-50"
        />
        <ListaAlertaDoms
          titulo="DOMs próximos a vencer"
          doms={metricas.doms_proximos_vencer}
          colorTexto="text-yellow-700"
          colorFondo="bg-yellow-50"
        />
      </div>

      {/* Productos pendientes en los próximos 15 días */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <h2 className="px-4 py-3 text-sm font-medium text-gray-700 border-b border-gray-200">
          Productos pendientes — próximos 15 días
        </h2>
        {metricas.productos_pendientes_15_dias.length === 0 ? (
          <p className="px-4 py-3 text-sm text-gray-400">Sin registros</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-[#1A56A0] text-white">
                <th className="text-left px-4 py-2 text-xs font-medium">Producto</th>
                <th className="text-left px-4 py-2 text-xs font-medium">Cant. pendiente</th>
                <th className="text-left px-4 py-2 text-xs font-medium">DOMs involucrados</th>
              </tr>
            </thead>
            <tbody>
              {metricas.productos_pendientes_15_dias.map((p, i) => (
                <tr key={p.nombre_producto} className={i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                  <td className="px-4 py-2 text-gray-700">{p.nombre_producto}</td>
                  <td className="px-4 py-2 text-gray-700">{p.cantidad_pendiente}</td>
                  <td className="px-4 py-2 text-gray-700">{p.doms_involucrados}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Bloque 4 — Cumplimiento */}
      {MOSTRAR_CUMPLIMIENTO && (
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <h2 className="px-4 py-3 text-sm font-medium text-gray-700 border-b border-gray-200">
          Cumplimiento
        </h2>
        <table className="w-full text-sm table-fixed">
          <thead>
            <tr className="bg-[#1A56A0] text-white">
              <th className="text-left px-4 py-2 text-xs font-medium w-1/3">Etapa</th>
              <th className="text-left px-4 py-2 text-xs font-medium w-1/3">Resultado</th>
              <th className="text-left px-4 py-2 text-xs font-medium w-1/3">Cumplimiento</th>
            </tr>
          </thead>
          <tbody>
            {FILAS_CUMPLIMIENTO.map((fila, i) => {
              const valor = metricas[fila.campo]
              // Las 5 filas llegan como { nivel, ok, total, porcentaje }; string como respaldo defensivo
              const nivel = typeof valor === 'string' ? valor : valor?.nivel
              const detalle = typeof valor === 'object' && valor?.porcentaje !== null
                ? `${valor.porcentaje}% (${valor.ok} de ${valor.total})`
                : null
              return (
                <tr key={fila.campo} className={i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                  <td className="px-4 py-2 text-gray-700">{fila.etiqueta}</td>
                  <td className="px-4 py-2">
                    <span className={`px-2 py-1 text-xs rounded-full font-medium ${ESTILOS_CUMPLIMIENTO[nivel] ?? ESTILOS_CUMPLIMIENTO.SIN_DATOS}`}>
                      {nivel}
                    </span>
                  </td>
                  <td className="px-4 py-2">
                    {detalle
                      ? <span className="px-2 py-1 text-xs rounded-full font-medium bg-[#1A56A0]/10 text-[#1A56A0]">{detalle}</span>
                      : <span className="text-xs text-gray-400">—</span>}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      )}
    </div>
  )
}

// Tarjeta simple con etiqueta y valor numérico
function TarjetaResumen({ label, valor }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</p>
      <p className="text-2xl font-semibold text-gray-800 mt-1">{valor}</p>
    </div>
  )
}

// Lista de DOMs para las alertas de vencimiento
function ListaAlertaDoms({ titulo, doms, colorTexto, colorFondo }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      <h2 className="px-4 py-3 text-sm font-medium text-gray-700 border-b border-gray-200">
        {titulo}
      </h2>
      {doms.length === 0 ? (
        <p className="px-4 py-3 text-sm text-gray-400">Sin registros</p>
      ) : (
        <ul className="divide-y divide-gray-100">
          {doms.map(dom => (
            <li key={dom.dom_id} className={`px-4 py-2 text-sm ${colorFondo} ${colorTexto}`}>
              <span className="font-medium">DOM #{dom.dom_id}</span>
              {' — '}
              {dom.nombre_cliente_detalle ?? '—'}
              {' — '}
              {formatearFecha(dom.fecha_criterio)}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default PaginaDashboard
