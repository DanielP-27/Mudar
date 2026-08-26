// src/context/AvisosContext.jsx
import { createContext, useContext } from 'react'
import { useAvisosCronometros } from '../hooks/useAvisosCronometros'

// Canal entre la franja, que vive en el Layout, y el cronómetro, que vive dentro del
// <Outlet/>. Sin él, quien finaliza un cronómetro y se queda en la pantalla seguiría
// viendo su propio aviso en la franja hasta navegar, y pensaría que no funcionó.
//
// El valor por omisión hace que consumirlo sin proveedor no rompa nada: los roles que no
// ven la franja tampoco consultan, y para ellos refrescar no tiene nada que refrescar.
const ContextoAvisos = createContext({ datos: null, fallo: false, refrescar: () => {} })

export function ProveedorAvisos({ habilitado, children }) {
  const avisos = useAvisosCronometros(habilitado)

  return (
    <ContextoAvisos.Provider value={avisos}>
      {children}
    </ContextoAvisos.Provider>
  )
}

// Hook para consumir el contexto — usar en cualquier componente
export const useAvisos = () => useContext(ContextoAvisos)
