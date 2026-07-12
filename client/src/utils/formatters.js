// src/utils/formatters.js
// Convierte string a integer (esto por diseño de arquitectura Django) — retorna null si está vacío
// actualmente solo se utiliza en PaginaCrearDom para hacer conversión de los campos nombre_cliente; tiempo_salida_almacen; rentabilidad
export const toInt = (valor) => valor !== '' ? parseInt(valor, 10) : null

// Formatea una fecha a dd/mm/aaaa (formato único de display en todo el sistema).
export const formatearFecha = (fecha) => {
  if (!fecha) return '—'
  if (fecha instanceof Date) {
    const dd = String(fecha.getDate()).padStart(2, '0')
    const mm = String(fecha.getMonth() + 1).padStart(2, '0')
    return `${dd}/${mm}/${fecha.getFullYear()}`
  }
  return fecha.slice(0, 10).split('-').reverse().join('/')
}