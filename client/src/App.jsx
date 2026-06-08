// src/App.jsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import ProtectedRoute from './routes/ProtectedRoute'
import RoleRoute, { ROLES } from './routes/RoleRoute'
import Layout from './components/layout/Layout'

// Páginas — se implementan en fases posteriores
import PaginaLogin        from './pages/auth/PaginaLogin'
import PaginaDashboard    from './pages/dashboard/PaginaDashboard'
import PaginaListaDoms    from './pages/doms/PaginaListaDoms'
import PaginaCrearDom     from './pages/doms/PaginaCrearDom'
import PaginaEditarDom    from './pages/doms/PaginaEditarDom'
import PaginaVerDom       from './pages/doms/PaginaVerDom'
import PaginaClientes     from './pages/catalogos/PaginaClientes'
import PaginaProductos    from './pages/catalogos/PaginaProductos'
import PaginaFamilias     from './pages/catalogos/PaginaFamilias'
import PaginaTurnos       from './pages/catalogos/PaginaTurnos'
import PaginaCumplimiento from './pages/informes/PaginaCumplimiento'
import PaginaDespachos    from './pages/informes/PaginaDespachos'
import PaginaAuditoria    from './pages/informes/PaginaAuditoria'

// Roles con acceso a catálogos
const ROLES_CATALOGOS = [ROLES.ADMIN, ROLES.GERENCIA]

// Roles con acceso a creación de DOMs
const ROLES_CREAR_DOM = [ROLES.ADMIN, ROLES.ANALISTA_1, ROLES.ANALISTA_2]

function App() {
  return (
    <BrowserRouter>
      <Routes>

        {/* Redirige raíz al dashboard */}
        <Route path="/" element={<Navigate to="/dashboard" replace />} />

        {/* Login — Layout en modo login, sidebar solo con logo */}
        <Route element={<Layout modoLogin={true} />}>
          <Route path="/login" element={<PaginaLogin />} />
        </Route>

        {/* Rutas protegidas — requieren autenticación */}
        <Route element={<ProtectedRoute />}>

          {/* Layout completo con sidebar y navegación */}
          <Route element={<Layout />}>

            {/* Dashboard — todos los roles */}
            <Route path="/dashboard" element={<PaginaDashboard />} />

            {/* DOMs — rutas estáticas primero, dinámicas después */}
            <Route path="/doms" element={<PaginaListaDoms />} />

            {/* Crear DOM — solo ADMIN, ANALISTA_1, ANALISTA_2 */}
            <Route element={<RoleRoute rolesPermitidos={ROLES_CREAR_DOM} />}>
              <Route path="/doms/crear" element={<PaginaCrearDom />} />
            </Route>

            {/* Rutas dinámicas — /doms/crear */}
            <Route path="/doms/:domId"        element={<PaginaVerDom />} />
            <Route path="/doms/:domId/editar" element={<PaginaEditarDom />} />

            {/* Informes — todos los roles */}
            <Route path="/informes/cumplimiento" element={<PaginaCumplimiento />} />
            <Route path="/informes/despachos"    element={<PaginaDespachos />} />
            <Route path="/informes/auditoria"    element={<PaginaAuditoria />} />

            {/* Catálogos — solo ADMIN y GERENCIA */}
            <Route element={<RoleRoute rolesPermitidos={ROLES_CATALOGOS} />}>
              <Route path="/clientes"  element={<PaginaClientes />} />
              <Route path="/productos" element={<PaginaProductos />} />
              <Route path="/familias"  element={<PaginaFamilias />} />
              <Route path="/turnos"    element={<PaginaTurnos />} />
            </Route>

          </Route>
        </Route>

        {/* Ruta no definida — redirige al dashboard */}
        <Route path="*" element={<Navigate to="/dashboard" replace />} />

      </Routes>
    </BrowserRouter>
  )
}

export default App