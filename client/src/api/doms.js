// src/api/doms.js
import api from './axios'

// Retorna listado de DOMs — acepta filtros opcionales como query params
export const obtenerDoms = (filtros = {}) =>
  api.get('/api/doms/', { params: filtros })

// Retorna el detalle completo de un DOM por su ID
export const obtenerDom = (domId) =>
  api.get(`/api/doms/${domId}/`)

// Crea un nuevo registro DOM con los datos del formulario
export const crearDom = (datos) =>
  api.post('/api/doms/', datos)

// Actualiza todos los campos de un DOM existente
export const actualizarDom = (domId, datos) =>
  api.put(`/api/doms/${domId}/`, datos)

// Desactiva un DOM — PATCH activo=false, nunca DELETE
export const desactivarDom = (domId) =>
  api.patch(`/api/doms/${domId}/`, { activo: false })

// Retorna registros de planeación — acepta filtros opcionales
export const obtenerPlaneacion = (filtros = {}) =>
  api.get('/api/planeacion/', { params: filtros })

// Crea un nuevo registro de planeación
export const crearPlaneacion = (datos) =>
  api.post('/api/planeacion/', datos)

// Actualiza un registro de planeación por su ID
export const actualizarPlaneacion = (registroId, datos) =>
  api.put(`/api/planeacion/${registroId}/`, datos)

// Retorna registros de almacén — acepta filtros opcionales
export const obtenerAlmacen = (filtros = {}) =>
  api.get('/api/almacen/', { params: filtros })

// Actualiza un registro de almacén por su ID
export const actualizarAlmacen = (registroId, datos) =>
  api.put(`/api/almacen/${registroId}/`, datos)

// Crea un nuevo registro de almacén asociado a una planeación
export const crearAlmacen = (datos) =>
  api.post('/api/almacen/', datos)

// Retorna registros de producción — acepta filtros opcionales
export const obtenerProduccion = (filtros = {}) =>
  api.get('/api/produccion/', { params: filtros })

// Actualiza un registro de producción por su ID
export const actualizarProduccion = (registroId, datos) =>
  api.put(`/api/produccion/${registroId}/`, datos)

// Crea un nuevo registro de producción asociado a una planeación
export const crearProduccion = (datos) =>
  api.post('/api/produccion/', datos)

// Retorna registros de tratamiento — acepta filtros opcionales
export const obtenerTratamiento = (filtros = {}) =>
  api.get('/api/tratamiento/', { params: filtros })

// Actualiza un registro de tratamiento por su ID
export const actualizarTratamiento = (registroId, datos) =>
  api.put(`/api/tratamiento/${registroId}/`, datos)

export const crearTratamiento = (datos) =>
  api.post('/api/tratamiento/', datos)

// Retorna registros de turnos día — acepta filtros opcionales
export const obtenerTurnosDia = (filtros = {}) =>
  api.get('/api/turnos-dia/', { params: filtros })

// Actualiza un registro de turno día por su ID
export const actualizarTurnoDia = (registroId, datos) =>
  api.put(`/api/turnos-dia/${registroId}/`, datos)

// Retorna el reporte consolidado de un DOM en formato PDF
export const obtenerReporteDom = (domId) =>
  api.get(`/api/reportes/dom/${domId}/`, { responseType: 'blob' })