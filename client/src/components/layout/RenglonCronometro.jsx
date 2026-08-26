// src/components/layout/RenglonCronometro.jsx
//
// Un cronómetro dentro de la franja. Es un enlace a la etapa de producción del DOM que
// lo contiene y NO lleva botón de finalizar: la colisión entre dos líderes se corrige
// sola porque navegar es lo que dispara el recálculo.
//
// El backend manda estado y valores; las palabras se eligen aquí.

import { Link } from 'react-router-dom'

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

function RenglonCronometro({ renglon, cerrado = false, alNavegar }) {
  const marca = cerrado ? null : frase(renglon)

  const filete = marca?.grave
    ? 'border-l-red-400 bg-red-50/60'
    : marca
      ? 'border-l-amber-400 bg-amber-50/60'
      : 'border-l-transparent'

  return (
    <Link
      to={destino(renglon)}
      onClick={alNavegar}
      className={`block border-b border-l-4 border-b-gray-100 px-3 py-2.5 hover:bg-gray-50 active:bg-gray-100 md:px-5 ${filete}`}
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
    </Link>
  )
}

export default RenglonCronometro
