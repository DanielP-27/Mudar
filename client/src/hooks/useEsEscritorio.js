import { useState, useEffect } from 'react'

// Responde "¿el viewport es de escritorio (>= 768px, breakpoint md: de Tailwind)?".
// Se usa para que el colapso del sidebar sea solo de escritorio y en móvil el
// drawer siempre muestre las etiquetas.
export function useEsEscritorio() {
  const consulta = '(min-width: 768px)'

  // Estado inicial: consultamos el ancho actual para no arrancar con un valor
  // equivocado (evita un parpadeo al montar).
  const [esEscritorio, setEsEscritorio] = useState(
    () => window.matchMedia(consulta).matches
  )

  useEffect(() => {
    const mql = window.matchMedia(consulta)
    const alCambiar = (e) => setEsEscritorio(e.matches)
    mql.addEventListener('change', alCambiar)
    return () => mql.removeEventListener('change', alCambiar)
  }, [])

  return esEscritorio
}
