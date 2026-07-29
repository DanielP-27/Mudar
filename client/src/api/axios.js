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

// Interceptor de respuesta — renueva la sesión y maneja errores globales
api.interceptors.response.use(
  (response) => {
    // Espeja la renovación deslizante del backend: toda respuesta exitosa
    // reinicia el contador local de inactividad.
    if (localStorage.getItem('mudar_usuario')) {
      localStorage.setItem('mudar_token_tiempo', Date.now().toString())
    }
    return response
  },
  (error) => {
    // El 401 del login significa credenciales incorrectas, no sesión vencida.
    // Ahí no hay sesión que limpiar ni a dónde redirigir: lo maneja la propia
    // pantalla de ingreso.
    const esLogin = error.config?.url?.includes('/api/auth/login/')

    if (error.response?.status === 401 && !esLogin) {
      localStorage.removeItem('mudar_usuario')
      localStorage.removeItem('mudar_token_tiempo')
      localStorage.removeItem('mudar_token_ventana')
      window.location.href = '/login?sesion=expirada'
    }
    return Promise.reject(error)
  }
)

export default api