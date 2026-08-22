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
    // El 401 del login significa credenciales incorrectas, no sesión vencida.
    // Ahí no hay sesión que limpiar ni a dónde redirigir: lo maneja la propia
    // pantalla de ingreso.
    // El 401 del logout significa que el token ya estaba muerto. El usuario
    // está saliendo de todos modos, así que expulsarlo con «sesión expirada»
    // sería un mensaje falso.
    const esLogin  = error.config?.url?.includes('/api/auth/login/')
    const esLogout = error.config?.url?.includes('/api/auth/logout/')

    if (error.response?.status === 401 && !esLogin && !esLogout) {
      localStorage.removeItem('mudar_usuario')
      window.location.href = '/login?sesion=expirada'
    }
    return Promise.reject(error)
  }
)

export default api