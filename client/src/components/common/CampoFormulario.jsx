// src/components/common/CampoFormulario.jsx
// Wrapper reutilizable de campo de formulario con label y soporte para obligatorio

function CampoFormulario({ label, obligatorio, children }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-medium text-gray-600 uppercase tracking-wide">
        {label}{obligatorio && <span className="text-red-500 ml-1">*</span>}
      </label>
      {children}
    </div>
  )
}

export default CampoFormulario
