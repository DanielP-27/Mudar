// src/utils/errores.js
// Traduce un error de axios en un mensaje legible para el usuario.
// El backend responde SIEMPRE con { error: <string> } y, solo en validaciones,
// además con { detalle: <serializer.errors> }. Este util extrae el mensaje más
// específico disponible y garantiza que SIEMPRE se devuelva un string
// (nunca un objeto, evitando "[object Object]" en pantalla).

// Recorre recursivamente el objeto `detalle` (serializer.errors de DRF) y lo
// convierte en una lista plana de líneas "campo: mensaje".
// No se exporta: es el motor interno del paso 2 de extraerMensajeError.
const aplanarDetalle = (detalle, prefijo = '') => {
  const lineas = []

  for (const [clave, valor] of Object.entries(detalle)) {
    // `non_field_errors` son validaciones cruzadas (validate() del serializer):
    // se muestran como frase completa, sin la etiqueta técnica.
    const etiqueta = clave === 'non_field_errors'
      ? prefijo
      : prefijo ? `${prefijo} · ${clave}` : clave

    if (Array.isArray(valor)) {
      valor.forEach((item, i) => {
        if (item && typeof item === 'object') {
          // Lista de objetos (serializer many=True, ej. productos): se recursa
          // por índice. Los items sin error llegan como {} y no aportan líneas.
          lineas.push(...aplanarDetalle(item, `${etiqueta} #${i + 1}`))
        } else {
          // Lista de strings: son los mensajes finales del campo (hoja).
          lineas.push(etiqueta ? `${etiqueta}: ${item}` : String(item))
        }
      })
    } else if (valor && typeof valor === 'object') {
      // Serializer anidado (dict): se recursa manteniendo la etiqueta como prefijo.
      lineas.push(...aplanarDetalle(valor, etiqueta))
    } else {
      // Valor string suelto (caso raro): se muestra tal cual.
      lineas.push(etiqueta ? `${etiqueta}: ${valor}` : String(valor))
    }
  }

  return lineas
}

// API pública. Devuelve el mensaje más específico disponible en el error,
// bajando de lo específico a lo genérico. `fallback` es el texto contextual
// del llamador para cuando la respuesta no trae nada reconocible.
export const extraerMensajeError = (err, fallback = 'Ocurrió un error inesperado.') => {
  // Paso 1 — el servidor nunca respondió (sin red / caído).
  if (!err?.response) {
    return 'Sin conexión con el servidor. Verifique su red e intente de nuevo.'
  }

  const data = err.response.data

  // Paso 2 — errores de validación por campo (lo más específico).
  if (data?.detalle) {
    const lineas = aplanarDetalle(data.detalle)
    if (lineas.length) return lineas.join('\n')
  }

  // Paso 3 — mensaje de negocio / permiso / 404 / 500 de nuestras vistas.
  if (typeof data?.error === 'string') return data.error

  // Paso 4 — llave nativa de DRF (auth, 404 de router, etc.).
  if (typeof data?.detail === 'string') return data.detail

  // Paso 5 — red de seguridad: nada reconocible en el cuerpo.
  return fallback
}
