// src/components/common/AvisoSuelo.jsx
// Aviso bajo un campo numérico cuando el valor tecleado queda por debajo de su suelo.
//
// No impide guardar: el sistema señala y no bloquea, igual que CampoRequeridoCierre.
// La garantía real vive en el backend, declarada una sola vez en server/models.py —el
// validador del campo y el CheckConstraint de la tabla—. Esto es comodidad: avisa
// mientras el usuario todavía mira el campo, en vez de hacerlo con un modal cuando ya
// pulsó guardar y cambió de foco.
//
// ⚠️ Los dos textos son IDÉNTICOS a los del backend (MENSAJE_MAYOR_QUE_CERO y
// MENSAJE_NO_NEGATIVO en server/models.py) para que quien ignore el aviso y guarde lea
// la misma frase en el modal de error. Viven en dos sitios porque cruzan el límite entre
// Python y JavaScript, y no hay forma de compartirlos: si cambian allá, cambian aquí.

function AvisoSuelo({ valor, minimo }) {
  // El vacío se comprueba ANTES de convertir: Number('') es 0, así que sin esta línea
  // un campo de suelo 1 recién abierto avisaría desde el primer render. Y además la
  // ausencia es legítima — lo obligatorio se exige al cerrar la etapa, no al escribir.
  if (valor === '' || valor === null || valor === undefined) return null

  // Number y no parseInt: parseInt('5x') devuelve 5, Number('5x') devuelve NaN. Aquí
  // interesa lo segundo, no dar por bueno un número que arrastra basura detrás.
  const numero = Number(valor)
  if (Number.isNaN(numero) || numero >= minimo) return null

  return (
    <p className="text-sm font-semibold text-amber-600 mt-1">
      {minimo === 1 ? 'Debe ser mayor a 0' : 'No puede ser negativo'}
    </p>
  )
}

export default AvisoSuelo
