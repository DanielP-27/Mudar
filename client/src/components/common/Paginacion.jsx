// src/components/common/Paginacion.jsx
// Barra de paginación reutilizable (móvil y escritorio). Es solo presentacional:
// recibe la página actual, el total de páginas y el total de registros, y avisa
// al padre con onPagina(nuevaPagina). La lógica (slice, POR_PAGINA, reset/clamp)
// vive en cada página porque depende de sus datos. Centralizar el markup evita
// repetir esta barra arriba y abajo de cada tabla del sistema.

import { FiChevronLeft, FiChevronRight } from 'react-icons/fi'

function Paginacion({ pagina, totalPaginas, total, onPagina }) {
  return (
    <div className="flex items-center justify-between px-4 py-3 bg-white rounded-lg border border-gray-200">
      <span className="text-xs text-gray-500">
        Página {pagina} de {totalPaginas} — {total} registros
      </span>
      <div className="flex items-center gap-2">
        <button
          onClick={() => onPagina(pagina - 1)}
          disabled={pagina === 1}
          className="p-1.5 rounded border border-gray-300 text-gray-600
                     hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed">
          <FiChevronLeft size={15} />
        </button>
        <button
          onClick={() => onPagina(pagina + 1)}
          disabled={pagina === totalPaginas}
          className="p-1.5 rounded border border-gray-300 text-gray-600
                     hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed">
          <FiChevronRight size={15} />
        </button>
      </div>
    </div>
  )
}

export default Paginacion
