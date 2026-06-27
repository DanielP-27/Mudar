// src/components/common/SelectSiNo.jsx
// Par de radio buttons Sí/No — reemplaza el <select> de dos opciones booleanas.
// value/onChange usan el mismo contrato que antes: 'true' | 'false' | ''
function SelectSiNo({ name, value, onChange, disabled }) {
  return (
    <div className={`flex items-center gap-4 ${disabled ? 'opacity-60' : ''}`}>
      <label className="flex items-center gap-1.5 text-sm text-gray-700 cursor-pointer">
        <input type="radio" name={name} value="true"
          checked={value === 'true'}
          onChange={() => onChange('true')}
          disabled={disabled}
          className="accent-[#1A56A0]" />
        Sí
      </label>
      <label className="flex items-center gap-1.5 text-sm text-gray-700 cursor-pointer">
        <input type="radio" name={name} value="false"
          checked={value === 'false'}
          onChange={() => onChange('false')}
          disabled={disabled}
          className="accent-[#1A56A0]" />
        No
      </label>
    </div>
  )
}

export default SelectSiNo
