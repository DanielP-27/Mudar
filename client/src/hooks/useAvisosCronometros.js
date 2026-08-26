// src/hooks/useAvisosCronometros.js
import { useCallback, useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { consultarAvisos } from '../api/cronometro'

// Ventana en la que se ignora un foco repetido. El alt-tab de ida y vuelta no debe
// disparar dos consultas; volver a la pestaña diez minutos después, sí.
const ANTIRREBOTE_MS = 3000

// Cuánto dura el destello. Una sola vez por cambio, no mientras dure el estado.
const PULSO_MS = 1200

// Compara la respuesta nueva con la anterior y devuelve qué merece un destello.
//
// La regla es una sola: destella la APARICIÓN DE UNA MARCA, venga en un renglón nuevo o
// en uno que ya estaba. No destella un cronómetro nuevo sin marcas — es el evento más
// frecuente del día, no pide nada a nadie, y como iniciar dispara un refresco, el líder
// se estaría avisando a sí mismo de lo que acaba de hacer. Tampoco destella que un
// renglón desaparezca, que es una buena noticia, ni que una marca siga encendida, que
// es lo que convertiría el aviso en ruido de fondo.
function delta(previo, nuevo) {
  if (!previo || !nuevo) return null

  const antes = new Map(previo.sin_finalizar.map((r) => [r.id, r]))
  const cerradosAntes = new Set(previo.cerrados_recientes.map((r) => r.id))

  let hallazgo = null
  const anotar = (grave) => {
    if (grave || !hallazgo) hallazgo = grave ? 'grave' : 'aviso'
  }

  // Un renglón que no estaba se compara contra «sin ninguna marca»: así, aparecer ya
  // marcado destella, y aparecer limpio no.
  const SIN_MARCAS = { turno_terminado: false, pausa_larga: false, por_terminar: false }

  for (const r of nuevo.sin_finalizar) {
    const anterior = antes.get(r.id) ?? SIN_MARCAS

    if (r.turno_terminado && !anterior.turno_terminado) anotar(true)
    if (r.pausa_larga && !anterior.pausa_larga) anotar(true)
    if (r.por_terminar && !anterior.por_terminar) anotar(false)
  }

  // Que el sistema cierre un cronómetro es grave: acaba de sustituir el dato de alguien.
  for (const r of nuevo.cerrados_recientes) {
    if (!cerradosAntes.has(r.id)) anotar(true)
  }

  return hallazgo
}

// habilitado: los roles que no pueden consultar el endpoint tampoco lo piden. La guarda
// del servidor sigue ahí y es la que manda; ésta evita pedir lo que ya sabemos que van a
// negar, y que un planeador quede en «no se pudo consultar» de forma permanente.
export function useAvisosCronometros(habilitado = true) {
  const [datos, setDatos] = useState(null)   // null = todavía no hay respuesta válida
  const [fallo, setFallo] = useState(false)
  const [pulso, setPulso] = useState(null)   // null | 'aviso' | 'grave'

  // Número de la última petición lanzada. Es un ref y no un estado porque se lee en la
  // misma ejecución en que se escribe, y porque cambiarlo no debe repintar nada.
  const peticionVigente = useRef(0)
  const ultimaConsulta = useRef(0)

  // La respuesta anterior, para comparar. En ref y no en estado: sirve para decidir, no
  // para pintar, y guardarla como estado provocaría un repintado de más por consulta.
  const anterior = useRef(null)

  const consultar = useCallback(async () => {
    if (!habilitado) return

    // Cada petición se queda con su número; el contador guarda cuál fue la última.
    const mia = ++peticionVigente.current
    ultimaConsulta.current = Date.now()

    try {
      const { data } = await consultarAvisos()
      // Las respuestas no vuelven en el orden en que salieron. Sin esta comparación,
      // una lenta puede pisar a una posterior y devolver a la lista de activos un
      // cronómetro que el barrido ya cerró.
      if (mia === peticionVigente.current) {
        const hallazgo = delta(anterior.current, data)
        anterior.current = data
        setDatos(data)
        setFallo(false)
        if (hallazgo) setPulso(hallazgo)
      }
    } catch {
      if (mia === peticionVigente.current) setFallo(true)
    }
  }, [habilitado])

  // 1 — Al navegar. El ?etapa= no cambia el pathname, así que moverse entre pestañas
  // de un DOM no genera tráfico.
  const { pathname } = useLocation()
  useEffect(() => { consultar() }, [pathname, consultar])

  // 2 — Al recuperar el foco de la pestaña, para el usuario concentrado que no navega.
  // Renueva el token, y se acepta: ese evento implica presencia humana, que es
  // justamente lo que la caducidad deslizante quiere premiar.
  useEffect(() => {
    const alVolver = () => {
      if (Date.now() - ultimaConsulta.current > ANTIRREBOTE_MS) consultar()
    }
    window.addEventListener('focus', alVolver)
    return () => window.removeEventListener('focus', alVolver)
  }, [consultar])

  // El destello se apaga solo. Una vez por cambio y no mientras dure el estado: es la
  // diferencia entre avisar y machacar.
  useEffect(() => {
    if (!pulso) return
    const temporizador = setTimeout(() => setPulso(null), PULSO_MS)
    return () => clearTimeout(temporizador)
  }, [pulso])

  // 3 — Tras cada acción sobre un cronómetro. Lo consume el contexto del Layout: quien
  // cierra un cronómetro y se queda en la pantalla debe ver desaparecer su propio aviso.
  return { datos, fallo, pulso, refrescar: consultar }
}
