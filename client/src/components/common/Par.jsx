// src/components/common/Par.jsx
// Componente etiqueta:valor para las tarjetas móviles siguiendo el patrón doble
// marcado, para que si es necesario cambiar el estilo de las tarjetas, solo sea
// tocar el componente y todo el código relacionado con las filas.

function Par({ etiqueta, children }) {
  return (
    <div className="flex justify-between gap-3 py-1">
      <span className="text-xs text-gray-500 shrink-0">{etiqueta}</span>
      <span className="text-sm text-gray-800 text-right">{children}</span>
    </div>
  )
}

export default Par
