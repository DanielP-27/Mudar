// src/components/ui/Spinner.jsx
import { FiLoader } from 'react-icons/fi'

// Indicador de carga — centrado en pantalla completa
function Spinner() {
  return (
    <div className="flex items-center justify-center h-screen w-full">
      <FiLoader
        size={32}
        className="animate-spin text-[#1A56A0]"
        aria-label="Cargando"
      />
    </div>
  )
}

export default Spinner