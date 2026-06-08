// src/api/catalogos.js
import api from './axios'

// Retorna listado de clientes — acepta filtros opcionales
export const obtenerClientes = (filtros = {}) =>
  api.get('/api/clientes/', { params: filtros })

// Retorna el detalle de un cliente por su ID
export const obtenerCliente = (clienteId) =>
  api.get(`/api/clientes/${clienteId}/`)

// Crea un nuevo cliente con los datos del formulario
export const crearCliente = (datos) =>
  api.post('/api/clientes/', datos)

// Actualiza todos los campos de un cliente existente
export const actualizarCliente = (clienteId, datos) =>
  api.put(`/api/clientes/${clienteId}/`, datos)

// Desactiva un cliente — PATCH activo=false, nunca DELETE
export const desactivarCliente = (clienteId) =>
  api.patch(`/api/clientes/${clienteId}/`, { activo: false })

// Retorna listado de familias de producto — acepta filtros opcionales
export const obtenerFamilias = (filtros = {}) =>
  api.get('/api/familias/', { params: filtros })

// Retorna el detalle de una familia por su ID
export const obtenerFamilia = (familiaId) =>
  api.get(`/api/familias/${familiaId}/`)

// Crea una nueva familia de producto
export const crearFamilia = (datos) =>
  api.post('/api/familias/', datos)

// Desactiva una familia de producto — PATCH activo=false, nunca DELETE
export const desactivarFamilia = (familiaId) =>
  api.patch(`/api/familias/${familiaId}/`, { activo: false })

// Retorna listado de productos — acepta filtros opcionales
export const obtenerProductos = (filtros = {}) =>
  api.get('/api/productos/', { params: filtros })

// Retorna el detalle de un producto por su ID
export const obtenerProducto = (productoId) =>
  api.get(`/api/productos/${productoId}/`)

// Crea un nuevo producto con los datos del formulario
export const crearProducto = (datos) =>
  api.post('/api/productos/', datos)

// Actualiza todos los campos de un producto existente
export const actualizarProducto = (productoId, datos) =>
  api.put(`/api/productos/${productoId}/`, datos)

// Desactiva un producto — PATCH activo=false, nunca DELETE
export const desactivarProducto = (productoId) =>
  api.patch(`/api/productos/${productoId}/`, { activo: false })

// Retorna listado de turnos — acepta filtros opcionales
export const obtenerTurnos = (filtros = {}) =>
  api.get('/api/turnos/', { params: filtros })

// Retorna el detalle de un turno por su ID
export const obtenerTurno = (turnoId) =>
  api.get(`/api/turnos/${turnoId}/`)

// Crea un nuevo turno con los datos del formulario
export const crearTurno = (datos) =>
  api.post('/api/turnos/', datos)

// Actualiza todos los campos de un turno existente
export const actualizarTurno = (turnoId, datos) =>
  api.put(`/api/turnos/${turnoId}/`, datos)

// Desactiva un turno — PATCH activo=false, nunca DELETE
export const desactivarTurno = (turnoId) =>
  api.patch(`/api/turnos/${turnoId}/`, { activo: false })

// Retorna listado de listas predefinidas — tipos DOM, responsables, etc.
export const obtenerListas = (filtros = {}) =>
  api.get('/api/listas/', { params: filtros })

// Retorna el detalle de una lista predefinida por su ID
export const obtenerLista = (listaId) =>
  api.get(`/api/listas/${listaId}/`)

// Retorna listas predefinidas filtradas por tipo — usado en dropdowns del sistema
export const obtenerListasPorTipo = (tipo) =>
  api.get('/api/listas/', { params: { tipo, activo: true } })