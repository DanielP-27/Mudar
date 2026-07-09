// src/components/common/SelectSiNo.jsx

// Par de radio buttons Sí/No — reemplaza el <select> de dos opciones booleanas.
// value/onChange usan el mismo contrato que antes: 'true' | 'false' | ''
function SelectSiNo({ name, value, onChange, disabled, soloLectura }) {
  // Solo lectura por rol (soloLectura): usada EXCLUSIVAMENTE en el campo de bloqueo de cada
  // etapa cuando el usuario no puede editarla. Los radios nativos deshabilitados los agrisa el
  // navegador y no se lee cuál fue diligenciado; en su lugar se muestra el valor como una pill
  // sólida ámbar de alto contraste: "Sí" / "No", o "—" si aún no se ha diligenciado.
  // El resto de campos (y los editores) usan los radios normales de abajo.
  if (soloLectura) {
    const seleccionado = value === 'true' || value === 'false'
    const texto = value === 'true' ? 'Sí' : value === 'false' ? 'No' : '—'
    return (
      <span className={`inline-flex items-center px-3 py-1 rounded-md text-sm font-semibold ${
        seleccionado ? 'bg-amber-500 text-white' : 'bg-gray-100 text-gray-400 border border-gray-200'
      }`}>
        {texto}
      </span>
    )
  }

  return (
    <div className="flex items-center gap-4">
      <label className={`flex items-center gap-1.5 text-sm text-gray-700 ${disabled ? 'cursor-not-allowed' : 'cursor-pointer'}`}>
        <input type="radio" name={name} value="true"
          checked={value === 'true'}
          onChange={() => onChange('true')}
          disabled={disabled}
          className="accent-[#1A56A0] disabled:accent-black" />
        Sí
      </label>
      <label className={`flex items-center gap-1.5 text-sm text-gray-700 ${disabled ? 'cursor-not-allowed' : 'cursor-pointer'}`}>
        <input type="radio" name={name} value="false"
          checked={value === 'false'}
          onChange={() => onChange('false')}
          disabled={disabled}
          className="accent-[#1A56A0] disabled:accent-black" />
        No
      </label>
    </div>
  )
}

export default SelectSiNo
