// src/components/common/Toast.jsx
// Toast flotante fijo para feedback de éxito (no bloqueante). Se ancla al
// viewport (position: fixed) para que sea visible sin importar el scroll de la
// página. Es CONTROLADO: el padre pasa `mensaje` (o null) y maneja el auto-cierre
// (ver mostrarExito). Al aparecer se desliza desde la derecha.

import { useState, useEffect } from 'react'
import { FiCheckCircle } from 'react-icons/fi'

function Toast({ mensaje }) {
  // Estado de animación: al montar con mensaje, en el siguiente frame pasa a
  // visible para disparar la transición de entrada (slide-in).
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    if (!mensaje) { setVisible(false); return }
    const id = requestAnimationFrame(() => setVisible(true))
    return () => cancelAnimationFrame(id)
  }, [mensaje])

  if (!mensaje) return null

  return (
    <div
      role="status"
      aria-live="polite"
      className={`fixed top-5 right-5 z-50 flex items-center gap-2 max-w-sm
                  bg-white border border-green-200 border-l-4 border-l-green-600
                  rounded-lg shadow-lg px-4 py-3 text-sm font-medium text-gray-800
                  transition-all duration-300
                  ${visible ? 'translate-x-0 opacity-100' : 'translate-x-full opacity-0'}`}
    >
      <FiCheckCircle className="text-green-600 shrink-0" size={18} />
      <span>{mensaje}</span>
    </div>
  )
}

export default Toast
