// src/components/common/TypeaheadInput.jsx
// Componente reutilizable de búsqueda con sugerencias en tiempo real

function TypeaheadInput({ valor, onChange, sugerencias, mostrar, onSeleccionar,
                          obtenerLabel, obtenerKey, placeholder, disabled = false }) {
  return (
    <div className="relative w-full">
      <input type="text" value={valor} onChange={onChange}
        placeholder={placeholder}
        disabled={disabled}
        className="campo-input w-full disabled:bg-gray-50 disabled:text-gray-500"
        autoComplete="off" />
      {mostrar && sugerencias.length > 0 && (
        <ul className="absolute z-10 w-full bg-white border border-gray-200
                       rounded shadow-md mt-1 max-h-48 overflow-y-auto">
          {sugerencias.map(item => (
            <li key={obtenerKey(item)}
              onClick={() => onSeleccionar(item)}
              className="px-3 py-2 text-sm hover:bg-blue-50 cursor-pointer">
              {obtenerLabel(item)}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default TypeaheadInput
