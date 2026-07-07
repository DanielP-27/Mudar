// src/components/common/ModalMensaje.jsx
// Modal reutilizable para mostrar mensajes al usuario (validaciones, errores de
// negocio, etc.). Es un componente CONTROLADO: el padre es dueño del estado y
// pasa `abierto`/`mensaje`; el modal solo avisa cuándo cerrar vía `onCerrar`.
// Soporta multilínea: si el mensaje trae varias líneas (unidas con '\n' por el
// util extraerMensajeError), se renderizan como viñetas.

import { useEffect } from 'react'
import { FiAlertTriangle } from 'react-icons/fi'

function ModalMensaje({ abierto, titulo = 'Revise la información', mensaje, onCerrar }) {
  // El hook va SIEMPRE antes de cualquier return (Regla de Hooks). El listener
  // de Esc solo se registra cuando el modal está abierto y se limpia al cerrar.
  useEffect(() => {
    if (!abierto) return
    const alPresionar = e => { if (e.key === 'Escape') onCerrar() }
    window.addEventListener('keydown', alPresionar)
    return () => window.removeEventListener('keydown', alPresionar)
  }, [abierto, onCerrar])

  if (!abierto) return null

  // Parte el mensaje en líneas para decidir entre viñetas (multilínea) o párrafo.
  const lineas = (mensaje ?? '').split('\n').filter(Boolean)

  return (
    // Clic en el fondo cierra; clic dentro de la tarjeta no burbujea (stopPropagation).
    <div
      onClick={onCerrar}
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
    >
      <div
        onClick={e => e.stopPropagation()}
        className="bg-white rounded-lg shadow-xl border border-gray-200 border-t-4 border-t-amber-500 p-6 max-w-md w-full mx-4"
      >
        <div className="flex items-start gap-3 mb-4">
          <FiAlertTriangle className="text-amber-500 shrink-0 mt-0.5" size={22} />
          <h3 className="text-sm font-semibold text-amber-700">{titulo}</h3>
        </div>

        {lineas.length > 1 ? (
          <ul className="list-disc pl-5 space-y-1 text-sm text-gray-700 mb-5">
            {lineas.map((linea, i) => <li key={i}>{linea}</li>)}
          </ul>
        ) : (
          <p className="text-sm text-gray-700 mb-5">{lineas[0] ?? ''}</p>
        )}

        <div className="flex justify-end">
          <button
            autoFocus
            onClick={onCerrar}
            className="px-4 py-2 text-sm font-medium text-white bg-[#1A56A0] rounded hover:bg-[#134080]"
          >
            Entendido
          </button>
        </div>
      </div>
    </div>
  )
}

export default ModalMensaje
