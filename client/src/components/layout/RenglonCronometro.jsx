// src/components/layout/RenglonCronometro.jsx

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { revisarCronometro } from '../../api/cronometro'

// La etapa de producción es 'etapa4' en la URL aunque la pantalla la rotule «Etapa 5»:
// los identificadores de pestaña arrancan en etapa0.
const ETAPA_PRODUCCION = 'etapa4'

// El destino lleva los tres números que identifican la cadena. La planeación y la
// producción son numero_registro, únicos dentro de su padre por unique_together, así que
// la terna resuelve un registro y sólo uno. La pantalla los traduce a su índice.
function destino(renglon) {
  return `/doms/${renglon.dom_id}/editar`
    + `?etapa=${ETAPA_PRODUCCION}`
    + `&planeacion=${renglon.planeacion}`
    + `&produccion=${renglon.produccion}`
}

// Tres estados y no dos: sin la fecha explícita, un renglón sin nada podría ser de hoy,
// no tener fecha, o estar mal pintado, y el líder creería haber olvidado un cronómetro.
function cuando(renglon) {
  if (renglon.es_hoy) return 'Hoy'
  return renglon.fecha_planeacion ?? 'Sin fecha'
}

// La marca es una frase con el dato dentro, no un término en mayúsculas: el proyecto ya
// arrastra cuatro vocabularios de etiquetas y no conviene acuñar un quinto.
function frase(renglon) {
  if (renglon.pausa_larga) {
    return { texto: `En pausa desde las ${renglon.en_pausa_desde}`, grave: true }
  }
  if (renglon.turno_terminado) {
    return { texto: `Su turno terminó a las ${renglon.hora_salida} del ${cuando(renglon)}`, grave: true }
  }
  if (renglon.por_terminar) {
    return { texto: `Su turno termina a las ${renglon.hora_salida}`, grave: false }
  }
  return null
}

const MOTIVOS = {
  TECHO_JORNADA: 'Superó el tope de la jornada',
  PAUSA_ABANDONADA: 'Pausa abandonada',
}

function RenglonCronometro({ renglon, cerrado = false, alNavegar, puedeRevisar = false, alRevisar }) {
  const marca = cerrado ? null : frase(renglon)
  const [enviando, setEnviando] = useState(false)
  const navegar = useNavigate()

  const filete = marca?.grave
    ? 'border-l-red-400 bg-red-50/60'
    : marca
      ? 'border-l-amber-400 bg-amber-50/60'
      : 'border-l-transparent'

  const pideAccion = cerrado || renglon.estado === 'PAUSADO'
  const rotulo = pideAccion && puedeRevisar ? 'Revisar' : 'Ver'

  function abrir() {
    alNavegar?.()
    navegar(destino(renglon))
  }

  // Sólo los cerrados se marcan: un pausado sale de la franja cuando alguien lo reanuda,
  // no cuando alguien lo mira, y si se consulta sin reanudar el aviso debe seguir ahí.
  //
  // Marcar antes de navegar: la navegación desmonta este componente y dejaría la petición
  // a medio vuelo. Y si falla NO se navega, o el registro se vería como ya atendido.
  async function revisarYAbrir() {
    if (!(cerrado && puedeRevisar)) return abrir()

    setEnviando(true)
    try {
      await revisarCronometro(renglon.id)
      await alRevisar?.()
      abrir()
    } catch {
      setEnviando(false)
    }
  }

  return (
    <div className={`flex items-center border-b border-l-4 border-b-gray-100 ${filete}`}>
    <div
      // min-w-0 no es adorno: sin él un texto largo empujaría el botón fuera de la fila
      // en vez de recortarse. Sin hover, porque esta zona ya no responde al clic.
      className="min-w-0 flex-1 px-3 py-2.5 md:px-5"
    >
      <p className="font-mono text-sm font-semibold text-gray-800">
        DOM {renglon.dom_id} · Planeación #{renglon.planeacion} · Producción #{renglon.produccion}
      </p>

      <p className="text-xs text-gray-500">
        {renglon.inicio_por ? `Inició ${renglon.inicio_por}` : 'Sin usuario registrado'}
        {/* Un cerrado no lleva fecha de planeación: la pregunta de ese renglón no es
            cuándo se planeó, sino cuándo dejó de ser creíble. */}
        {cerrado
          ? ` · terminó el ${renglon.fin}`
          : ` · ${cuando(renglon)}${renglon.hora_salida ? ` · sale ${renglon.hora_salida}` : ''}`}
      </p>

      {marca && (
        <p className={`mt-0.5 text-sm font-semibold ${marca.grave ? 'text-red-700' : 'text-amber-700'}`}>
          {marca.texto}
        </p>
      )}

      {/* cerrado_por_sistema llega en el renglón y no se pinta: al usuario le importa
          cuándo terminó su producción, no cuándo corrió el barrido. El campo sigue
          decidiendo qué entra en esta sección —la ventana de 48 h se mide sobre él— y
          queda disponible si algún día hace falta explicar un cierre. */}
      {cerrado && (
        <p className="mt-0.5 font-mono text-xs text-gray-600">
          {MOTIVOS[renglon.motivo_cierre] ?? renglon.motivo_cierre}
          {' · '}{renglon.minutos_totales} min registrados
        </p>
      )}
    </div>

      {/* aria-label con el DOM dentro: tres botones seguidos rotulados «Ver» son
          indistinguibles para un lector de pantalla. */}
      <button
        type="button"
        onClick={revisarYAbrir}
        disabled={enviando}
        aria-label={`${rotulo} DOM ${renglon.dom_id}`}
        className="mr-3 flex-none rounded border border-gray-300 bg-white px-3 py-2 text-xs font-semibold text-gray-700 hover:bg-gray-100 active:bg-gray-200 disabled:opacity-50 md:mr-5"
      >
        {enviando ? 'Guardando…' : rotulo}
      </button>
    </div>
  )
}

export default RenglonCronometro
