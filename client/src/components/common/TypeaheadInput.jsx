// src/components/common/TypeaheadInput.jsx
// Componente reutilizable de búsqueda con sugerencias en tiempo real

import { useRef, useState } from 'react'

function TypeaheadInput({ valor, onChange, sugerencias, mostrar, onSeleccionar,
                          obtenerLabel, obtenerKey, placeholder, disabled = false }) {
  // Sugerencia resaltada con el teclado o el ratón; -1 = ninguna.
  const [indice, setIndice] = useState(-1)

  // Lista nueva = índice inválido: se reinicia en el render, no en un useEffect, para que Enter nunca elija con el índice viejo.
  const [sugerenciasPrevias, setSugerenciasPrevias] = useState(sugerencias)
  if (sugerencias !== sugerenciasPrevias) {
    setSugerenciasPrevias(sugerencias)
    setIndice(-1)
  }

  // REVISAR — estado interno: la lista se pinta si la página dice `mostrar` Y el usuario no pulsó Escape (`oculta`).
  const [oculta, setOculta] = useState(false)

  const abierta = mostrar && !oculta && sugerencias.length > 0
  const listaRef = useRef(null)

  // Solo las flechas desplazan la lista; el ratón no, para que no tiemble bajo el puntero.
  function mover(nuevo) {
    setIndice(nuevo)
    listaRef.current?.children[nuevo]?.scrollIntoView({ block: 'nearest' })
  }

  // Extremos: el resaltado se queda, como en un <select>. Enter sin resaltado no elige.
  function manejarTecla(e) {
    if (e.key === 'ArrowDown' && oculta) {
      e.preventDefault()
      setOculta(false)
      return
    }
    if (!abierta) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      mover(Math.min(indice + 1, sugerencias.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      mover(indice > 0 ? indice - 1 : indice)
    } else if (e.key === 'Enter' && indice >= 0) {
      e.preventDefault()
      onSeleccionar(sugerencias[indice])
    } else if (e.key === 'Escape') {
      e.preventDefault()
      setOculta(true)
      setIndice(-1)
    }
  }

  function manejarCambio(e) {
    setOculta(false)
    onChange(e)
  }

  return (
    <div className="relative w-full">
      <input type="text" value={valor} onChange={manejarCambio}
        onKeyDown={manejarTecla}
        placeholder={placeholder}
        disabled={disabled}
        className="campo-input w-full disabled:bg-gray-100 disabled:text-gray-700"
        autoComplete="off" />
      {abierta && (
        <ul ref={listaRef} className="absolute z-10 w-full bg-white border border-gray-200
                       rounded shadow-md mt-1 max-h-48 overflow-y-auto">
          {sugerencias.map((item, i) => (
            <li key={obtenerKey(item)}
              onClick={() => onSeleccionar(item)}
              onMouseEnter={() => setIndice(i)}
              className={`px-3 py-2 text-sm cursor-pointer ${i === indice ? 'bg-blue-50' : ''}`}>
              {obtenerLabel(item)}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default TypeaheadInput
