// src/components/layout/Layout.jsx
import { useState } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAutenticacion } from '../../context/AuthContext'
import { ROLES } from '../../routes/RoleRoute'
import Spinner from '../ui/Spinner'

// Iconos de react-icons
import { MdDashboard, MdMenu } from 'react-icons/md'
import { BsFileEarmarkText, BsPlusCircle, BsPencil, BsXCircle } from 'react-icons/bs'
import { FiUsers, FiBox, FiClock, FiBarChart2, FiChevronDown, FiChevronUp } from 'react-icons/fi'

// Importación logo Mudar
import logo_mudar from '../../assets/logo_mudar.png'

// Roles con acceso a catálogos
const ROLES_CATALOGOS = [ROLES.ADMIN, ROLES.GERENCIA]

// Roles con permiso de crear DOM
const ROLES_CREAR_DOM = [ROLES.ADMIN, ROLES.ANALISTA_1, ROLES.ANALISTA_2]

// Roles con permiso de desactivar DOM
const ROLES_DESACTIVAR_DOM = [ROLES.ADMIN]

function Layout({ modoLogin = false }) {
  const { usuario, cerrarSesion }   = useAutenticacion()
  const [expandido, setExpandido]   = useState(!modoLogin)
  // control de submenús abiertos — objeto { clave: boolean }
  const [menuAbierto, setMenuAbierto] = useState({})
  const navegar = useNavigate()

  // Alterna el estado abierto/cerrado de un submenú
  const toggleMenu = (clave) => {
    setMenuAbierto(prev => ({ ...prev, [clave]: !prev[clave] }))
  }

  // Cierra sesión y redirige al login
  const manejarCerrarSesion = () => {
    cerrarSesion()
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

      {/* ── Sidebar ─────────────────────────────────────────────── */}
      <aside className={`
        flex flex-col bg-[#1A56A0] text-white transition-all duration-200
        ${expandido ? 'w-64' : 'w-14'}
      `}>

        {/* Logo + nombre app */}
        <div className={`border-b border-white/15
          ${expandido
            ? 'flex items-center gap-3 px-3 py-4'
            : 'flex flex-col items-center py-4 gap-2'
          }`}>
          <img src={logo_mudar} alt="Mudar de Colombia"
              className="w-8 h-8 object-contain flex-shrink-0" />
          {expandido && (
            <span className="text-xs font-medium leading-tight flex-1">
              App Gestión DOM'S<br />Mudar de Colombia
            </span>
          )}
          {!modoLogin && (
            <button
              onClick={() => setExpandido(prev => !prev)}
              className="text-white hover:text-white/70"
              aria-label="Alternar sidebar">
              <MdMenu size={20} />
            </button>
          )}
        </div>

        {/* Navegación — oculta en modo login */}
        {!modoLogin && (
          <nav className="flex-1 overflow-y-auto py-3 space-y-1 px-2">

            {/* Dashboard — sin submenú */}
            <NavLink
              to="/dashboard"
              className={({ isActive }) => `
                flex items-center gap-3 px-2 py-2 rounded text-sm
                ${isActive ? 'bg-white/20 font-medium' : 'hover:bg-white/10'}
              `}
            >
              <MdDashboard size={18} className="flex-shrink-0" />
              {expandido && <span>Dashboard</span>}
            </NavLink>

            {/* DOMs — con submenú acordeón */}
            <div>
              <button
                onClick={() => expandido && toggleMenu('doms')}
                className="w-full flex items-center gap-3 px-2 py-2 rounded text-sm
                           hover:bg-white/10"
              >
                <BsFileEarmarkText size={18} className="flex-shrink-0" />
                {expandido && (
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
              {expandido && menuAbierto['doms'] && (
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
                {/* Clientes */}
                <div>
                  <button
                    onClick={() => expandido && toggleMenu('clientes')}
                    className="w-full flex items-center gap-3 px-2 py-2 rounded text-sm
                               hover:bg-white/10"
                  >
                    <FiUsers size={18} className="flex-shrink-0" />
                    {expandido && (
                      <>
                        <span className="flex-1 text-left">Clientes</span>
                        {menuAbierto['clientes']
                          ? <FiChevronUp size={14} />
                          : <FiChevronDown size={14} />
                        }
                      </>
                    )}
                  </button>
                  {expandido && menuAbierto['clientes'] && (
                    <div className="ml-7 mt-1 space-y-1">
                      <NavLink to="/clientes?accion=crear"
                        className={({ isActive }) => `flex items-center gap-2 px-2 py-1.5 rounded text-xs ${isActive ? 'bg-white/20 font-medium' : 'hover:bg-white/10'}`}>
                        <BsPlusCircle size={13} /><span>Crear cliente</span>
                      </NavLink>
                      <NavLink to="/clientes?accion=editar"
                        className={({ isActive }) => `flex items-center gap-2 px-2 py-1.5 rounded text-xs ${isActive ? 'bg-white/20 font-medium' : 'hover:bg-white/10'}`}>
                        <BsPencil size={13} /><span>Editar cliente</span>
                      </NavLink>
                      <NavLink to="/clientes?accion=desactivar"
                        className={({ isActive }) => `flex items-center gap-2 px-2 py-1.5 rounded text-xs ${isActive ? 'bg-white/20 font-medium' : 'hover:bg-white/10'}`}>
                        <BsXCircle size={13} /><span>Desactivar cliente</span>
                      </NavLink>
                    </div>
                  )}
                </div>

                {/* Productos */}
                <div>
                  <button
                    onClick={() => expandido && toggleMenu('productos')}
                    className="w-full flex items-center gap-3 px-2 py-2 rounded text-sm
                               hover:bg-white/10"
                  >
                    <FiBox size={18} className="flex-shrink-0" />
                    {expandido && (
                      <>
                        <span className="flex-1 text-left">Productos</span>
                        {menuAbierto['productos']
                          ? <FiChevronUp size={14} />
                          : <FiChevronDown size={14} />
                        }
                      </>
                    )}
                  </button>
                  {expandido && menuAbierto['productos'] && (
                    <div className="ml-7 mt-1 space-y-1">
                      <NavLink to="/familias?accion=crear"
                        className={({ isActive }) => `flex items-center gap-2 px-2 py-1.5 rounded text-xs ${isActive ? 'bg-white/20 font-medium' : 'hover:bg-white/10'}`}>
                        <BsPlusCircle size={13} /><span>Crear familia</span>
                      </NavLink>
                      <NavLink to="/familias?accion=desactivar"
                        className={({ isActive }) => `flex items-center gap-2 px-2 py-1.5 rounded text-xs ${isActive ? 'bg-white/20 font-medium' : 'hover:bg-white/10'}`}>
                        <BsXCircle size={13} /><span>Desactivar familia</span>
                      </NavLink>
                      <NavLink to="/productos?accion=crear"
                        className={({ isActive }) => `flex items-center gap-2 px-2 py-1.5 rounded text-xs ${isActive ? 'bg-white/20 font-medium' : 'hover:bg-white/10'}`}>
                        <BsPlusCircle size={13} /><span>Crear producto</span>
                      </NavLink>
                      <NavLink to="/productos?accion=editar"
                        className={({ isActive }) => `flex items-center gap-2 px-2 py-1.5 rounded text-xs ${isActive ? 'bg-white/20 font-medium' : 'hover:bg-white/10'}`}>
                        <BsPencil size={13} /><span>Editar producto</span>
                      </NavLink>
                      <NavLink to="/productos?accion=desactivar"
                        className={({ isActive }) => `flex items-center gap-2 px-2 py-1.5 rounded text-xs ${isActive ? 'bg-white/20 font-medium' : 'hover:bg-white/10'}`}>
                        <BsXCircle size={13} /><span>Desactivar producto</span>
                      </NavLink>
                    </div>
                  )}
                </div>

                {/* Turnos */}
                <div>
                  <button
                    onClick={() => expandido && toggleMenu('turnos')}
                    className="w-full flex items-center gap-3 px-2 py-2 rounded text-sm
                               hover:bg-white/10"
                  >
                    <FiClock size={18} className="flex-shrink-0" />
                    {expandido && (
                      <>
                        <span className="flex-1 text-left">Turnos</span>
                        {menuAbierto['turnos']
                          ? <FiChevronUp size={14} />
                          : <FiChevronDown size={14} />
                        }
                      </>
                    )}
                  </button>
                  {expandido && menuAbierto['turnos'] && (
                    <div className="ml-7 mt-1 space-y-1">
                      <NavLink to="/turnos?accion=crear"
                        className={({ isActive }) => `flex items-center gap-2 px-2 py-1.5 rounded text-xs ${isActive ? 'bg-white/20 font-medium' : 'hover:bg-white/10'}`}>
                        <BsPlusCircle size={13} /><span>Crear turno</span>
                      </NavLink>
                      <NavLink to="/turnos?accion=editar"
                        className={({ isActive }) => `flex items-center gap-2 px-2 py-1.5 rounded text-xs ${isActive ? 'bg-white/20 font-medium' : 'hover:bg-white/10'}`}>
                        <BsPencil size={13} /><span>Editar turno</span>
                      </NavLink>
                      <NavLink to="/turnos?accion=desactivar"
                        className={({ isActive }) => `flex items-center gap-2 px-2 py-1.5 rounded text-xs ${isActive ? 'bg-white/20 font-medium' : 'hover:bg-white/10'}`}>
                        <BsXCircle size={13} /><span>Desactivar turno</span>
                      </NavLink>
                    </div>
                  )}
                </div>
              </>
            )}

            {/* Informes — todos los roles */}
            <div>
              <button
                onClick={() => expandido && toggleMenu('informes')}
                className="w-full flex items-center gap-3 px-2 py-2 rounded text-sm
                           hover:bg-white/10"
              >
                <FiBarChart2 size={18} className="flex-shrink-0" />
                {expandido && (
                  <>
                    <span className="flex-1 text-left">Informes</span>
                    {menuAbierto['informes']
                      ? <FiChevronUp size={14} />
                      : <FiChevronDown size={14} />
                    }
                  </>
                )}
              </button>
              {expandido && menuAbierto['informes'] && (
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
              {expandido && (
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
        <header className="flex items-center gap-4 px-5 py-3 bg-white
                           border-b border-gray-200 flex-shrink-0">
          <div className="flex-1" id="topbar-titulo" />
        </header>

        {/* Contenido de la página activa */}
        <main className="flex-1 overflow-y-auto p-5">
          <Outlet />
        </main>

      </div>
    </div>
  )
}

export default Layout