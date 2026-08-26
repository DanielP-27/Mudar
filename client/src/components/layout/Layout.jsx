// src/components/layout/Layout.jsx
import { useState } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAutenticacion } from '../../context/AuthContext'
import { ROLES } from '../../routes/RoleRoute'
import FranjaCronometros from './FranjaCronometros'
import { ProveedorAvisos } from '../../context/AvisosContext'
import Spinner from '../ui/Spinner'
import { useEsEscritorio } from '../../hooks/useEsEscritorio'

// Iconos de react-icons
import { MdDashboard, MdMenu } from 'react-icons/md'
import { BsFileEarmarkText, BsPlusCircle, BsPencil, BsXCircle } from 'react-icons/bs'
import { FiUsers, FiBox, FiBarChart2, FiChevronDown, FiChevronUp, FiX } from 'react-icons/fi'

// Importación logo Mudar
import logo_mudar from '../../assets/logo_mudar.png'

// Roles con acceso a catálogos
const ROLES_CATALOGOS = [ROLES.ADMIN, ROLES.GERENCIA]

// Roles con permiso de crear DOM
const ROLES_CREAR_DOM = [ROLES.ADMIN, ROLES.ANALISTA_1, ROLES.ANALISTA_2]

// Roles con permiso de desactivar DOM
const ROLES_DESACTIVAR_DOM = [ROLES.ADMIN]

// Roles con permiso para visualizar el componente de franja. Repite la lista de
// CronometroAvisosView a propósito: la del backend es seguridad y no se toca; ésta
// evita pedir lo que ya sabemos que van a negar, y de paso que un planeador quede en
// «no se pudo consultar» de forma permanente. Si cambia una, cambia la otra.
const ROLES_FRANJA = [ROLES.ADMIN, ROLES.LIDER_PLANTA, ROLES.GERENCIA]

// Módulo de informes CONGELADO hasta después de la V1.0 (2026-08-05).
// Las 3 pantallas son placeholders: el menú prometía algo que no existe.
// Las rutas y los archivos siguen en su sitio; solo se oculta la entrada.
// Para reactivarlo, poner en true.
const MOSTRAR_INFORMES = false

function Layout({ modoLogin = false }) {
  const { usuario, cerrarSesion }   = useAutenticacion()
  const [expandido, setExpandido]   = useState(!modoLogin)
  // control de submenús abiertos — objeto { clave: boolean }
  const [menuAbierto, setMenuAbierto] = useState({})
  const navegar = useNavigate()

  // Drawer (móvil): panel del sidebar abierto/cerrado. En escritorio no aplica.
  const [drawerAbierto, setDrawerAbierto] = useState(false)

  // El colapso (barra angosta w-14) es SOLO de escritorio; en móvil el sidebar
  // va siempre completo, con etiquetas. Ver hook useEsEscritorio.
  const esEscritorio = useEsEscritorio()
  const colapsado = esEscritorio && !expandido

  // Alterna el estado abierto/cerrado de un submenú
  const toggleMenu = (clave) => {
    setMenuAbierto(prev => ({ ...prev, [clave]: !prev[clave] }))
  }

  // Cierra sesión y redirige al login
  const manejarCerrarSesion = async () => {
    await cerrarSesion()
    navegar('/login', { replace: true })
  }

  // Iniciales del usuario para el avatar
  const iniciales = usuario?.nombre_completo
    ?.split(' ')
    .map(n => n[0])
    .slice(0, 2)
    .join('')
    .toUpperCase() ?? '??'

  // Etiqueta legible del rol
  const ETIQUETAS_ROL = {
    GERENCIA:     'Gerencia',
    ADMIN:        'Administrador',
    ANALISTA_1:   'Analista 1',
    ANALISTA_2:   'Analista 2',
    PLANEADOR:    'Planeador',
    LIDER_PLANTA: 'Líder de Planta',
  }

  return (
    <div className="flex h-screen overflow-hidden bg-gray-100">

      {/* Overlay del drawer — solo móvil; al tocar, cierra */}
      {drawerAbierto && (
        <div onClick={() => setDrawerAbierto(false)}
             className="fixed inset-0 bg-black/40 z-30 md:hidden" />
      )}

      {/* ── Sidebar ─────────────────────────────────────────────── */}
      {/* Móvil: drawer fijo fuera del lienzo que entra deslizando (translate-x).
          Escritorio (md:): vuelve al flujo y conserva el colapso w-64/w-14. */}
      <aside className={`
        flex flex-col bg-[#1A56A0] text-white z-40
        fixed inset-y-0 left-0 w-64
        transition-transform duration-200
        ${drawerAbierto ? 'translate-x-0' : '-translate-x-full'}
        md:static md:translate-x-0 md:transition-all
        ${expandido ? 'md:w-64' : 'md:w-14'}
      `}>

        {/* Logo + nombre app */}
        <div className={`border-b border-white/15
          ${colapsado
            ? 'flex flex-col items-center py-4 gap-2'
            : 'flex items-center gap-3 px-3 py-4'
          }`}>
          <img src={logo_mudar} alt="Mudar de Colombia"
              className="w-8 h-8 object-contain flex-shrink-0" />
          {!colapsado && (
            <span className="text-xs font-medium leading-tight flex-1">
              App Gestión DOM'S<br />Mudar de Colombia
            </span>
          )}
          {!modoLogin && (
            <button
              onClick={() => setExpandido(prev => !prev)}
              className="hidden md:block text-white hover:text-white/70"
              aria-label="Alternar sidebar">
              <MdMenu size={20} />
            </button>
          )}
          {/* Cerrar el drawer — solo móvil */}
          {!modoLogin && (
            <button
              onClick={() => setDrawerAbierto(false)}
              className="md:hidden text-white hover:text-white/70"
              aria-label="Cerrar menú">
              <FiX size={20} />
            </button>
          )}
        </div>

        {/* Navegación — oculta en modo login */}
        {!modoLogin && (
          <nav onClick={(e) => e.target.closest('a') && setDrawerAbierto(false)}
               className="flex-1 overflow-y-auto py-3 space-y-1 px-2">

            {/* Dashboard — sin submenú */}
            <NavLink
              to="/dashboard"
              className={({ isActive }) => `
                flex items-center gap-3 px-2 py-2 rounded text-sm
                ${isActive ? 'bg-white/20 font-medium' : 'hover:bg-white/10'}
              `}
            >
              <MdDashboard size={18} className="flex-shrink-0" />
              {!colapsado && <span>Dashboard</span>}
            </NavLink>

            {/* DOMs — con submenú acordeón */}
            <div>
              <button
                onClick={() => !colapsado && toggleMenu('doms')}
                className="w-full flex items-center gap-3 px-2 py-2 rounded text-sm
                           hover:bg-white/10"
              >
                <BsFileEarmarkText size={18} className="flex-shrink-0" />
                {!colapsado && (
                  <>
                    <span className="flex-1 text-left">DOMs</span>
                    {menuAbierto['doms']
                      ? <FiChevronUp size={14} />
                      : <FiChevronDown size={14} />
                    }
                  </>
                )}
              </button>

              {/* Submenú DOMs */}
              {!colapsado && menuAbierto['doms'] && (
                <div className="ml-7 mt-1 space-y-1">
                  {ROLES_CREAR_DOM.includes(usuario?.rol) && (
                    <NavLink to="/doms/crear"
                      className={({ isActive }) => `
                        flex items-center gap-2 px-2 py-1.5 rounded text-xs
                        ${isActive ? 'bg-white/20 font-medium' : 'hover:bg-white/10'}
                      `}>
                      <BsPlusCircle size={13} />
                      <span>Crear DOM</span>
                    </NavLink>
                  )}
                  <NavLink to="/doms"
                    className={({ isActive }) => `
                      flex items-center gap-2 px-2 py-1.5 rounded text-xs
                      ${isActive ? 'bg-white/20 font-medium' : 'hover:bg-white/10'}
                    `}>
                    <BsPencil size={13} />
                    <span>Editar DOM</span>
                  </NavLink>
                  {ROLES_DESACTIVAR_DOM.includes(usuario?.rol) && (
                    <NavLink to="/doms?accion=desactivar"
                      className={({ isActive }) => `
                        flex items-center gap-2 px-2 py-1.5 rounded text-xs
                        ${isActive ? 'bg-white/20 font-medium' : 'hover:bg-white/10'}
                      `}>
                      <BsXCircle size={13} />
                      <span>Desactivar DOM</span>
                    </NavLink>
                  )}
                </div>
              )}
            </div>

            {/* Catálogos — solo ADMIN y GERENCIA */}
            {ROLES_CATALOGOS.includes(usuario?.rol) && (
              <>
                {/* Clientes — sin submenú */}
                <NavLink
                  to="/clientes"
                  className={({ isActive }) => `
                    flex items-center gap-3 px-2 py-2 rounded text-sm
                    ${isActive ? 'bg-white/20 font-medium' : 'hover:bg-white/10'}
                  `}
                >
                  <FiUsers size={18} className="flex-shrink-0" />
                  {!colapsado && <span>Clientes</span>}
                </NavLink>

                {/* Productos — sin submenú */}
                <NavLink
                  to="/productos"
                  className={({ isActive }) => `
                    flex items-center gap-3 px-2 py-2 rounded text-sm
                    ${isActive ? 'bg-white/20 font-medium' : 'hover:bg-white/10'}
                  `}
                >
                  <FiBox size={18} className="flex-shrink-0" />
                  {!colapsado && <span>Productos</span>}
                </NavLink>
              </>
            )}

            {/* Informes — todos los roles */}
            {MOSTRAR_INFORMES && (
            <div>
              <button
                onClick={() => !colapsado && toggleMenu('informes')}
                className="w-full flex items-center gap-3 px-2 py-2 rounded text-sm
                           hover:bg-white/10"
              >
                <FiBarChart2 size={18} className="flex-shrink-0" />
                {!colapsado && (
                  <>
                    <span className="flex-1 text-left">Informes</span>
                    {menuAbierto['informes']
                      ? <FiChevronUp size={14} />
                      : <FiChevronDown size={14} />
                    }
                  </>
                )}
              </button>
              {!colapsado && menuAbierto['informes'] && (
                <div className="ml-7 mt-1 space-y-1">
                  <NavLink to="/informes/cumplimiento"
                    className={({ isActive }) => `flex items-center gap-2 px-2 py-1.5 rounded text-xs ${isActive ? 'bg-white/20 font-medium' : 'hover:bg-white/10'}`}>
                    <FiBarChart2 size={13} /><span>Cumplimiento planeación</span>
                  </NavLink>
                  <NavLink to="/informes/despachos"
                    className={({ isActive }) => `flex items-center gap-2 px-2 py-1.5 rounded text-xs ${isActive ? 'bg-white/20 font-medium' : 'hover:bg-white/10'}`}>
                    <FiBarChart2 size={13} /><span>Cumplimiento despachos</span>
                  </NavLink>
                  <NavLink to="/informes/auditoria"
                    className={({ isActive }) => `flex items-center gap-2 px-2 py-1.5 rounded text-xs ${isActive ? 'bg-white/20 font-medium' : 'hover:bg-white/10'}`}>
                    <FiBarChart2 size={13} /><span>Auditoría</span>
                  </NavLink>
                </div>
              )}
            </div>
            )}

          </nav>
        )}

        {/* Usuario + rol — oculto en modo login */}
        {!modoLogin && usuario && (
          <div className="border-t border-white/15 px-3 py-3">
            <div className="flex items-center gap-2">
              {/* Avatar con iniciales */}
              <div className="w-8 h-8 rounded-full bg-white/20 flex items-center
                              justify-content-center text-xs font-bold flex-shrink-0
                              flex justify-center items-center">
                {iniciales}
              </div>
              {!colapsado && (
                <div className="overflow-hidden">
                  <p className="text-xs font-medium truncate">
                    {usuario.nombre_completo}
                  </p>
                  <p className="text-xs text-white/60 truncate">
                    {ETIQUETAS_ROL[usuario.rol] ?? usuario.rol}
                  </p>
                  <button
                    onClick={manejarCerrarSesion}
                    className="text-xs text-white/50 hover:text-white mt-1"
                  >
                    Cerrar sesión
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </aside>

      {/* ── Área principal ──────────────────────────────────────── */}
      <div className="flex flex-col flex-1 overflow-hidden">

        {/* Topbar */}
        <header className="flex items-center gap-4 px-4 md:px-5 py-3
                           bg-[#1A56A0] md:bg-white
                           border-b border-white/15 md:border-gray-200 flex-shrink-0">
          {/* Marca + hamburguesa para abrir el drawer — solo móvil */}
          {!modoLogin && (
            <div className="flex md:hidden items-center flex-1">
              <img src={logo_mudar} alt="Mudar de Colombia"
                   className="w-8 h-8 object-contain" />
              <button onClick={() => setDrawerAbierto(true)}
                      className="ml-auto text-white hover:text-white/70"
                      aria-label="Abrir menú">
                <MdMenu size={24} />
              </button>
            </div>
          )}
          <div className="hidden md:block flex-1" id="topbar-titulo" />
        </header>

        {/* El proveedor envuelve a la franja y al <Outlet/> para que el cronómetro, que
            vive dentro, pueda pedir un refresco tras cada acción. */}
        <ProveedorAvisos habilitado={ROLES_FRANJA.includes(usuario?.rol)}>

          {/* Franja de cronómetros — hermana del <Outlet/>, no hija: aquí no se desmonta
              al navegar, así que sobrevive con su estado. Y queda fija sin necesidad de
              position, porque en esta columna solo desplaza el <main>. */}
          {ROLES_FRANJA.includes(usuario?.rol) && <FranjaCronometros />}

          {/* Contenido de la página activa */}
          <main className="flex-1 overflow-y-auto p-3 md:p-5">
            <Outlet />
          </main>

        </ProveedorAvisos>

      </div>
    </div>
  )
}

export default Layout