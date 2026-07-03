// src/components/common/SelectSiNo.jsx
import { FiLock } from 'react-icons/fi'

// Par de radio buttons Sí/No — reemplaza el <select> de dos opciones booleanas.
// value/onChange usan el mismo contrato que antes: 'true' | 'false' | ''
function SelectSiNo({ name, value, onChange, disabled, mostrarCandado }) {
  return (
    <div className="flex items-center gap-4">
      <label className={`flex items-center gap-1.5 text-sm text-gray-700 ${disabled ? 'cursor-not-allowed' : 'cursor-pointer'}`}>
        <input type="radio" name={name} value="true"
          checked={value === 'true'}
          onChange={() => onChange('true')}
          disabled={disabled}
          className={`accent-[#1A56A0] ${mostrarCandado ? '' : 'disabled:accent-black'}`} />
        Sí
      </label>
      <label className={`flex items-center gap-1.5 text-sm text-gray-700 ${disabled ? 'cursor-not-allowed' : 'cursor-pointer'}`}>
        <input type="radio" name={name} value="false"
          checked={value === 'false'}
          onChange={() => onChange('false')}
          disabled={disabled}
          className={`accent-[#1A56A0] ${mostrarCandado ? '' : 'disabled:accent-black'}`} />
        No
      </label>
      {disabled && mostrarCandado && (
        <FiLock className="text-gray-500" size={14} title="Solo lectura" />
      )}
    </div>
  )
}

export default SelectSiNo
