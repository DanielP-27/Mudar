// src/api/informes.js
import api from './axios'

// Retorna el informe de cumplimiento de planeación por rango de fechas
export const obtenerInformeCumplimiento = (fechaInicio, fechaFin) =>
  api.get('/api/informes/cumplimiento/', {
    params: { fecha_inicio: fechaInicio, fecha_fin: fechaFin }
  })

// Retorna el informe de cumplimiento de despachos por rango de fechas
export const obtenerInformeDespachos = (fechaInicio, fechaFin) =>
  api.get('/api/informes/despacho/', {
    params: { fecha_inicio: fechaInicio, fecha_fin: fechaFin }
  })

// Retorna el informe de auditoría — acepta filtros opcionales
export const obtenerInformeAuditoria = (filtros = {}) =>
  api.get('/api/informes/auditoria/', { params: filtros })