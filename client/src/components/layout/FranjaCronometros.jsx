// src/components/layout/FranjaCronometros.jsx
//
// Recordatorio de fin de jornada: qué cronómetros siguen abiertos y cuáles cerró el
// sistema. Vive en el Layout, entre la cabecera y el <main>, así que no se desmonta al
// navegar — de ahí que recuerde si está plegada sin guardarlo en ninguna parte.
//
// Nace SIEMPRE replegada y nunca se despliega sola. Está siempre presente, incluso
// vacía: su ausencia no puede confundirse con «no hay nada que avisar».

import { useState } from 'react'
import { FiChevronDown, FiChevronUp, FiClock } from 'react-icons/fi'
import { useAvisos } from '../../context/AvisosContext'
import RenglonCronometro from './RenglonCronometro'

// La banda es SIEMPRE la misma: un instrumento, no una notificación. Si cambiara de
// color entera con cada estado, parecería un elemento distinto cada vez y el ojo no
// aprendería dónde mirar. Oscura porque no hay ninguna otra banda oscura en la
// aplicación —la cabecera es blanca en escritorio y el contenido gris claro—, así que
// se distingue sin competir con el azul institucional.
const BANDA = 'bg-slate-800 border-slate-900'

// El destello escala con la gravedad: ámbar si lo que apareció es un recordatorio, rojo
// si pide a alguien ahora. Sin movimiento y con transición, no con parpadeo: la franja
// avisa, no interrumpe. Y respeta prefers-reduced-motion, que en móvil está activo más a
// menudo de lo que se cree.
const PULSOS = {
  aviso: 'bg-amber-900',
  grave: 'bg-red-900',
}

// El estado lo llevan el punto y el color del texto. Sobre fondo oscuro el ámbar destaca
// mucho más que sobre un fondo ámbar pálido, que es donde hace falta que destaque.
const TEXTOS = {
  vacia:     'text-slate-300',
  callada:   'text-slate-100',
  alertando: 'text-amber-300 font-semibold',
  sinDatos:  'text-red-300 font-medium',
}

// El punto lleva el estado a forma además de a color: cuadrado cuando no hay dato.
const PUNTOS = {
  vacia:     'bg-slate-500 rounded-full',
  callada:   'bg-sky-400 rounded-full',
  alertando: 'bg-amber-400 rounded-full',
  sinDatos:  'bg-red-400 rounded-sm',
}

// Las tres marcas, declaradas una sola vez: si mañana aparece una cuarta, se añade aquí
// y el estado y el mensaje se enteran los dos.
const tieneMarca = (renglon) =>
  renglon.turno_terminado || renglon.por_terminar || renglon.pausa_larga

// Cuenta lo que la línea necesita saber sin recorrer dos veces la misma lista.
function resumir(datos) {
  const abiertos = datos.sin_finalizar.length
  return {
    abiertos,
    cerrados: datos.cerrados_recientes.length,
    marcados: datos.sin_finalizar.filter(tieneMarca).length,
  }
}

// El orden importa: sin datos se resuelve primero, porque una respuesta ausente no es
// una respuesta vacía. Y un cerrado reciente, por sí solo, NO enciende la alerta: ya no
// admite acción, así que sostener el ámbar 48 horas sería fatiga y no aviso. De que ha
// aparecido se encarga el pulso, una sola vez.
function estadoDe(resumen, fallo) {
  if (fallo || resumen === null) return 'sinDatos'
  if (resumen.abiertos === 0 && resumen.cerrados === 0) return 'vacia'
  return resumen.marcados > 0 ? 'alertando' : 'callada'
}

// La frase principal habla de lo abierto, que es lo accionable.
function frasePrincipal(estado, resumen) {
  if (estado === 'sinDatos') return 'No se pudo consultar'
  if (estado === 'vacia') return 'No hay cronómetros abiertos en el sistema actualmente'

  if (estado === 'alertando') {
    // Un conteo siempre con el mismo formato: el detalle está dentro, y es la razón de
    // desplegar. Enumerar motivos aquí no cabe en un teléfono.
    return `${resumen.marcados} de ${resumen.abiertos} requiere atención`
  }

  if (resumen.abiertos === 0) return 'No hay cronómetros abiertos'
  return resumen.abiertos === 1 ? '1 cronómetro en curso' : `${resumen.abiertos} cronómetros en curso`
}

// Segmento opcional, sólo si hay cerrados. Se oculta en pantallas estrechas para que la
// frase principal nunca se corte a mitad de palabra; el chevron sigue diciendo que hay más.
function fraseCerrados(resumen) {
  if (!resumen || resumen.cerrados === 0) return null
  return resumen.cerrados === 1
    ? '1 cerrado por el sistema'
    : `${resumen.cerrados} cerrados por el sistema`
}

// Las tres secciones son los tres estados del cronómetro. La gravedad ordena dentro de
// cada una —eso ya viene resuelto del servidor— pero no reparte entre ellas.
function Seccion({ titulo, cuantos, children }) {
  return (
    <>
      <p className="sticky top-0 border-b border-gray-200 bg-gray-100 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-gray-600 md:px-5">
        {titulo} · {cuantos}
      </p>
      {children}
    </>
  )
}

function FranjaCronometros() {
  const { datos, fallo, pulso } = useAvisos()
  const [desplegada, setDesplegada] = useState(false)

  const resumen = datos === null ? null : resumir(datos)
  const estado = estadoDe(resumen, fallo)
  const principal = frasePrincipal(estado, resumen)
  const cerrados = estado === 'sinDatos' ? null : fraseCerrados(resumen)

  const enCurso = datos?.sin_finalizar.filter((r) => r.estado !== 'PAUSADO') ?? []
  const pausados = datos?.sin_finalizar.filter((r) => r.estado === 'PAUSADO') ?? []
  const cerradosRecientes = datos?.cerrados_recientes ?? []
  const hayQueDesplegar = enCurso.length + pausados.length + cerradosRecientes.length > 0

  // El sistema puede cerrar el panel, nunca abrirlo. Si el usuario lo tenía abierto y la
  // respuesta llega sin nada, no queda qué mostrar; desplegarse solo sería interrumpir.
  const abierta = desplegada && hayQueDesplegar

  const linea = (
    <>
      {/* Icono y rótulo dan identidad: sin ellos el ojo lee «otra alerta» y aprende a
          saltarla. El rótulo se oculta en móvil, donde el ancho es lo escaso. */}
      <FiClock size={16} className="flex-none text-slate-400" aria-hidden="true" />
      <span className="hidden flex-none text-xs font-semibold uppercase tracking-wider text-slate-400 sm:inline">
        Cronómetros
      </span>

      <span className={`h-2.5 w-2.5 flex-none ${PUNTOS[estado]}`} aria-hidden="true" />
      <span className={`truncate ${TEXTOS[estado]}`}>
        {principal}
        {cerrados && <span className="hidden text-slate-400 sm:inline"> · {cerrados}</span>}
      </span>
    </>
  )

  const fondo = pulso ? PULSOS[pulso] : BANDA
  const clasesLinea =
    `flex w-full items-center gap-2.5 px-3 py-2.5 text-left text-base transition-colors duration-500 motion-reduce:transition-none md:px-5 ${fondo}`

  return (
    // role="status" en el contenedor y no en el botón: uno anuncia cambios y el otro
    // espera pulsaciones, y en el mismo elemento se contradicen.
    <div className="flex-shrink-0 border-b border-slate-900" role="status" aria-live="polite">
      {hayQueDesplegar ? (
        <button
          type="button"
          onClick={() => setDesplegada((v) => !v)}
          aria-expanded={abierta}
          aria-controls="franja-panel"
          className={`${clasesLinea} hover:bg-slate-700 active:bg-slate-700`}
        >
          {linea}

          {/* La palabra manda y la flecha acompaña: un chevron es una convención
              aprendida y esta franja tiene que entenderla todo el mundo en la planta.
              Va como <span> con aspecto de botón y no como <button>: la banda entera ya
              es el botón, y anidarlos sería HTML inválido y rompería el teclado. */}
          <span className="ml-auto flex flex-none items-center gap-1 rounded bg-slate-600 px-2 py-1 text-xs font-semibold text-slate-100">
            {abierta ? 'Ocultar' : 'Ver'}
            <span className="hidden sm:inline">detalle</span>
            {abierta
              ? <FiChevronUp size={14} aria-hidden="true" />
              : <FiChevronDown size={14} aria-hidden="true" />}
          </span>
        </button>
      ) : (
        <div className={clasesLinea}>{linea}</div>
      )}

      {abierta && (
        // Porcentaje en móvil, donde la altura de la ventana varía mucho entre
        // dispositivos; tope absoluto en escritorio, donde lo que importa es cuántos
        // renglones se ven y no qué fracción de pantalla ocupan. La lista llega ordenada
        // por gravedad, así que lo visible sin desplazar es siempre lo que pide atención.
        <div id="franja-panel" className="max-h-[45dvh] overflow-y-auto bg-white md:max-h-96">
          {enCurso.length > 0 && (
            <Seccion titulo="En curso" cuantos={enCurso.length}>
              {enCurso.map((r) => (
                <RenglonCronometro key={r.id} renglon={r} alNavegar={() => setDesplegada(false)} />
              ))}
            </Seccion>
          )}

          {pausados.length > 0 && (
            <Seccion titulo="Pausados" cuantos={pausados.length}>
              {pausados.map((r) => (
                <RenglonCronometro key={r.id} renglon={r} alNavegar={() => setDesplegada(false)} />
              ))}
            </Seccion>
          )}

          {cerradosRecientes.length > 0 && (
            <Seccion titulo="Cerrados por el sistema" cuantos={cerradosRecientes.length}>
              {cerradosRecientes.map((r) => (
                <RenglonCronometro key={r.id} renglon={r} cerrado alNavegar={() => setDesplegada(false)} />
              ))}
              <p className="px-3 py-2 text-center text-xs text-gray-400 md:px-5">
                Cerrados en las últimas 48 horas
              </p>
            </Seccion>
          )}
        </div>
      )}
    </div>
  )
}

export default FranjaCronometros
