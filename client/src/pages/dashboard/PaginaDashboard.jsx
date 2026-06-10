// src/pages/dashboard/PaginaDashboard.jsx
import { useState, useEffect } from 'react'
import { obtenerDashboard } from '../../api/dashboard'

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
      .catch(() => setError('Error al cargar el dashboard.'))
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

      {/* Bloque 1 — Tarjetas resumen */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <TarjetaResumen label="Total DOMs"             valor={metricas.total_doms} />
        <TarjetaResumen label="DOMs activos"           valor={metricas.total_doms_activos} />
        <TarjetaResumen label="DOMs cerrados"          valor={metricas.total_doms_cerrados} />
        <TarjetaResumen label="Cantidad elaborada"     valor={metricas.cantidad_elaborada_total} />
        <TarjetaResumen label="Cantidad pendiente"     valor={metricas.cantidad_pendiente_total} />
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
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <h2 className="px-4 py-3 text-sm font-medium text-gray-700 border-b border-gray-200">
          Cumplimiento
        </h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-[#1A56A0] text-white">
              <th className="text-left px-4 py-2 text-xs font-medium">Etapa</th>
              <th className="text-left px-4 py-2 text-xs font-medium">Resultado</th>
            </tr>
          </thead>
          <tbody>
            {FILAS_CUMPLIMIENTO.map((fila, i) => {
              const valor = metricas[fila.campo]
              return (
                <tr key={fila.campo} className={i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                  <td className="px-4 py-2 text-gray-700">{fila.etiqueta}</td>
                  <td className="px-4 py-2">
                    <span className={`px-2 py-1 text-xs rounded-full font-medium ${ESTILOS_CUMPLIMIENTO[valor] ?? ESTILOS_CUMPLIMIENTO.SIN_DATOS}`}>
                      {valor}
                    </span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
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
              {dom.fecha_solicitada_cliente
                ? new Date(dom.fecha_solicitada_cliente).toLocaleDateString('es-CO')
                : '—'}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default PaginaDashboard
