// src/pages/auth/PaginaLogin.jsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAutenticacion } from '../../context/AuthContext'

function PaginaLogin() {
  const { iniciarSesion }                       = useAutenticacion()
  const navegar                                 = useNavigate()
  const [nombreUsuario, setNombreUsuario]       = useState('')
  const [contrasena, setContrasena]             = useState('')
  const [cargando, setCargando]                 = useState(false)
  const [error, setError]                       = useState(null)

  const manejarSubmit = async (e) => {
    e.preventDefault()
    setCargando(true)
    setError(null)

    try {
      await iniciarSesion(nombreUsuario, contrasena)
      // Login exitoso — redirigir siempre al dashboard
      navegar('/dashboard', { replace: true })
    } catch (err) {
      // Error de credenciales o conexión
      setError(
        err.response?.status === 400
          ? 'Usuario o contraseña incorrectos.'
          : 'Error de conexión. Intente nuevamente.'
      )
    } finally {
      setCargando(false)
    }
  }

  return (
    <div className="flex items-center justify-center h-full">
      <div className="w-full max-w-sm">

        {/* Título */}
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-gray-800">Bienvenido a la aplicación de gestión de DOMS de Mudar de Colombia S.A.S.</h1>
          <p className="text-sm text-gray-500 mt-1">
            Por favor, digite sus datos para iniciar
          </p>
        </div>

        {/* Formulario */}
        <form onSubmit={manejarSubmit} className="space-y-5">

          {/* Campo nombre usuario */}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-gray-600 uppercase tracking-wide">
              Nombre usuario
            </label>
            <input
              type="text"
              value={nombreUsuario}
              onChange={e => setNombreUsuario(e.target.value)}
              required
              autoFocus
              className="border border-gray-300 rounded px-3 py-2 text-sm
                         focus:outline-none focus:border-[#1A56A0] focus:ring-1
                         focus:ring-[#1A56A0]"
            />
          </div>

          {/* Campo contraseña */}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-gray-600 uppercase tracking-wide">
              Contraseña
            </label>
            <input
              type="password"
              value={contrasena}
              onChange={e => setContrasena(e.target.value)}
              required
              className="border border-gray-300 rounded px-3 py-2 text-sm
                         focus:outline-none focus:border-[#1A56A0] focus:ring-1
                         focus:ring-[#1A56A0]"
            />
          </div>

          {/* Mensaje de error */}
          {error && (
            <p className="text-xs text-red-600 text-center">{error}</p>
          )}

          {/* Botón ingresar */}
          <button
            type="submit"
            disabled={cargando}
            className="w-full bg-[#1A56A0] text-white py-2 rounded text-sm
                       font-medium hover:bg-[#134080] disabled:opacity-60
                       disabled:cursor-not-allowed transition-colors"
          >
            {cargando ? 'Ingresando...' : 'INGRESAR'}
          </button>

        </form>
      </div>
    </div>
  )
}

export default PaginaLogin