// src/routes/ProtectedRoute.jsx
import { Navigate, Outlet } from 'react-router-dom'
import { useAutenticacion } from '../context/AuthContext'

function ProtectedRoute() {
  const { usuario, cargando } = useAutenticacion()

  // Esperar verificación de sesión antes de decidir redirigir
  if (cargando) return null

  // Sin usuario autenticado — redirigir a login
  if (!usuario) return <Navigate to="/login" replace />

  // Usuario autenticado — renderizar la página solicitada
  return <Outlet />
}

export default ProtectedRoute