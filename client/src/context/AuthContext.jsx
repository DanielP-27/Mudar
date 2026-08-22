// src/context/AuthContext.jsx
import { createContext, useContext, useState, useEffect } from 'react'
import { iniciarSesionApi, cerrarSesionApi, obtenerPerfil } from '../api/auth'

// Canal de comunicación del estado de autenticación hacia toda la app
const ContextoAutenticacion = createContext(null)

export function ProveedorAutenticacion({ children }) {
  // null = ningún usuario autenticado
  const [usuario, setUsuario]       = useState(null)
  // true mientras se verifica si hay sesión guardada
  const [cargando, setCargando]     = useState(true)

  // Al arrancar, la validez de la sesión la decide el servidor: se le pregunta
  // por el perfil con el token guardado.
  useEffect(() => {
    const revalidarSesion = async () => {
      const sesionGuardada = localStorage.getItem('mudar_usuario')

      if (!sesionGuardada) {
        setCargando(false)
        return
      }

      try {
        const { data }  = await obtenerPerfil()
        // PerfilView no devuelve el token: se conserva el guardado.
        const { token } = JSON.parse(sesionGuardada)
        setUsuario({ ...data.perfil, token })
      } catch (error) {
        // Un fallo de red no es un veredicto: la sesión se conserva y decidirá
        // la primera petición real. Del 401 se encarga el interceptor.
        if (!error.response) setUsuario(JSON.parse(sesionGuardada))
      }

      setCargando(false)
    }

    revalidarSesion()
  }, [])

// Llamada al backend — fusiona perfil y token en un objeto plano
const iniciarSesion = async (nombreUsuario, contrasena) => {
  const { data } = await iniciarSesionApi(nombreUsuario, contrasena)
  // { id, username, nombre_completo, rol, token }
  const datosUsuario = { ...data.perfil, token: data.token }

  // Actualizar estado en memoria
  setUsuario(datosUsuario)

  // Persistir la sesión; al recargar, su validez la decide el servidor
  localStorage.setItem('mudar_usuario', JSON.stringify(datosUsuario))

  // Retorna datosUsuario para que PaginaLogin pueda redirigir inmediatamente
  return datosUsuario
}

  const cerrarSesion = async () => {
    try {
      await cerrarSesionApi()
    } catch {
      // Sin respuesta del servidor el usuario sale igual: la salida local no
      // puede depender de la red.
    }

    setUsuario(null)
    localStorage.removeItem('mudar_usuario')
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