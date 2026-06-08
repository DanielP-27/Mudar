// src/api/axios.js
import axios from 'axios'

// Instancia base de Axios — todas las peticiones usan esta configuración
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
})

// Interceptor de petición — adjunta el token a cada request
api.interceptors.request.use(
  (config) => {
    const sesionGuardada = localStorage.getItem('mudar_usuario')
    if (sesionGuardada) {
      const { token } = JSON.parse(sesionGuardada)
      // Token DRF — formato requerido por el backend
      config.headers.Authorization = `Token ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Interceptor de respuesta — maneja errores globales
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Token expirado o inválido — limpiar sesión y redirigir al login
    if (error.response?.status === 401) {
      localStorage.removeItem('mudar_usuario')
      localStorage.removeItem('mudar_token_tiempo')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default api