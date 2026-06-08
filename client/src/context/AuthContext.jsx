// src/context/AuthContext.jsx
import { createContext, useContext, useState, useEffect } from 'react'
import api from '../api/axios'

// Canal de comunicación del estado de autenticación hacia toda la app
const ContextoAutenticacion = createContext(null)

export function ProveedorAutenticacion({ children }) {
  // null = ningún usuario autenticado
  const [usuario, setUsuario]       = useState(null)
  // true mientras se verifica si hay sesión guardada
  const [cargando, setCargando]     = useState(true)

  // Al arrancar, restaurar sesión desde localStorage si el token sigue vigente
  useEffect(() => {
    const sesionGuardada  = localStorage.getItem('mudar_usuario')
    const tiempoGuardado  = localStorage.getItem('mudar_token_tiempo')

    if (sesionGuardada && tiempoGuardado) {
      const minutosTranscurridos = (Date.now() - Number(tiempoGuardado)) / 60000
      const tiempoExpiracion     = Number(import.meta.env.VITE_TOKEN_EXPIRY_MINUTES)

      if (minutosTranscurridos < tiempoExpiracion) {
        // Token vigente — restaurar sesión
        setUsuario(JSON.parse(sesionGuardada))
      } else {
        // Token expirado — limpiar localStorage
        localStorage.removeItem('mudar_usuario')
        localStorage.removeItem('mudar_token_tiempo')
      }
    }

    // Verificación completada, desactivar estado de carga
    setCargando(false)
  }, [])

// Llamada al backend — fusiona perfil y token en un objeto plano
const iniciarSesion = async (nombreUsuario, contrasena) => {
  const { data } = await api.post(
    '/api/auth/login/',
    { username: nombreUsuario, password: contrasena }
  )
  // { id, username, nombre_completo, rol, token }
  const datosUsuario = { ...data.perfil, token: data.token }

  // Actualizar estado en memoria
  setUsuario(datosUsuario)

  // Persistir sesión y timestamp para validar expiración al recargar
  localStorage.setItem('mudar_usuario',      JSON.stringify(datosUsuario))
  localStorage.setItem('mudar_token_tiempo', Date.now().toString())

  // Retorna datosUsuario para que PaginaLogin pueda redirigir inmediatamente
  return datosUsuario
}

  // Limpiar estado en memoria y sesión persistida
  const cerrarSesion = () => {
    setUsuario(null)
    localStorage.removeItem('mudar_usuario')
    localStorage.removeItem('mudar_token_tiempo')
  }

  // Expone usuario, iniciarSesion, cerrarSesion y cargando a todos los componentes hijos
  return (
    <ContextoAutenticacion.Provider value={{ usuario, iniciarSesion, cerrarSesion, cargando }}>
      {children}
    </ContextoAutenticacion.Provider>
  )
}

// Hook para consumir el contexto — usar en cualquier componente
export const useAutenticacion = () => useContext(ContextoAutenticacion)