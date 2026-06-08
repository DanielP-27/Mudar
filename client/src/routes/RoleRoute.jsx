// src/routes/RoleRoute.jsx
import { Navigate, Outlet } from 'react-router-dom'
import { useAutenticacion } from '../context/AuthContext'
import Spinner from '../components/ui/Spinner'

// Roles disponibles en el sistema — deben coincidir exactamente con los valores del backend
export const ROLES = {
  GERENCIA:    'GERENCIA',
  ADMIN:       'ADMIN',
  ANALISTA_1:  'ANALISTA_1',
  ANALISTA_2:  'ANALISTA_2',
  PLANEADOR:   'PLANEADOR',
  LIDER_PLANTA:'LIDER_PLANTA',
}

function RoleRoute({ rolesPermitidos }) {
  const { usuario, cargando } = useAutenticacion()

  // Delega la visualización de carga al componente Spinner
  if (cargando) return <Spinner />

  // Sin usuario autenticado — redirigir a login
  if (!usuario) return <Navigate to="/login" replace />

  // Rol no autorizado para esta ruta — redirigir al dashboard
  if (!rolesPermitidos.includes(usuario.rol)) {
    return <Navigate to="/dashboard" replace />
  }

  // Usuario autenticado con rol autorizado — renderizar la página solicitada
  return <Outlet />
}

export default RoleRoute