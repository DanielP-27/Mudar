// src/api/auth.js
import api from './axios'

// Inicia sesión — retorna token y perfil del usuario
export const iniciarSesionApi = (username, password) =>
  api.post('/api/auth/login/', { username, password })

// Cierra sesión — invalida el token en el backend
export const cerrarSesionApi = () =>
  api.post('/api/auth/logout/')

// Retorna el perfil del usuario autenticado
export const obtenerPerfil = () =>
  api.get('/api/auth/perfil/')

// Retorna el listado completo de usuarios — solo ADMIN
export const obtenerUsuarios = () =>
  api.get('/api/auth/usuarios/')

// Retorna el detalle de un usuario específico por su ID
export const obtenerUsuario = (userId) =>
  api.get(`/api/auth/usuarios/${userId}/`)

// Restablece la contraseña del usuario autenticado
export const restablecerPassword = (datos) =>
  api.post('/api/auth/reestablecer-password/', datos)