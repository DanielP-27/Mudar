// src/components/common/ModalBase.jsx
// Modal genérico y ÚNICO patrón visual del sistema. Está parametrizado por:
//   - `variante`  → color de franja/título + ícono (info · confirmacion · peligro · exito)
//   - `acciones`  → 1 o 2 botones; regla fija: la salida segura a la izquierda y la
//                   acción que ejecuta el propósito del modal a la derecha.
// Comportamiento uniforme para todos: overlay con role/aria, cierre con Esc y con
// clic fuera de la tarjeta. Es un componente CONTROLADO: el padre es dueño del
// estado (`abierto`) y decide qué hace `onCerrar`.
//
// El cuerpo admite dos formas:
//   - `mensaje` (string o string[]): texto plano; si trae varias líneas se pinta en viñetas.
//   - `children`: contenido JSX enriquecido (negritas, resaltados, etc.).
//
// ModalMensaje se apoya en este componente como variante `info` de un solo botón,
// de modo que sus llamadas existentes siguen funcionando sin cambios.

import { useEffect } from 'react'
import { FiAlertTriangle, FiHelpCircle, FiCheckCircle } from 'react-icons/fi'

// Cada variante define su ícono y sus clases de color (franja superior, ícono, título).
const VARIANTES = {
  info:         { Icono: FiAlertTriangle, borde: 'border-t-amber-500',  icono: 'text-amber-500',  titulo: 'text-amber-700' },
  confirmacion: { Icono: FiHelpCircle,    borde: 'border-t-[#1A56A0]',  icono: 'text-[#1A56A0]',  titulo: 'text-[#1A56A0]' },
  peligro:      { Icono: FiAlertTriangle, borde: 'border-t-red-600',    icono: 'text-red-600',    titulo: 'text-red-700' },
  exito:        { Icono: FiCheckCircle,   borde: 'border-t-green-600',  icono: 'text-green-600',  titulo: 'text-green-700' },
}

// Semántica de color del botón: azul = acción recomendada/continuar, rojo = acción
// destructiva/cancelar, outline = descartar neutral.
const ESTILOS_BOTON = {
  primario:   'text-white bg-[#1A56A0] hover:bg-[#134080]',
  peligro:    'text-white bg-red-600 hover:bg-red-700',
  secundario: 'text-gray-600 border border-gray-300 hover:bg-gray-50',
}

function ModalBase({
  abierto,
  variante = 'info',
  titulo = 'Revise la información',
  mensaje,
  children,
  acciones,
  nota,
  apilarBotones = false,
  onCerrar,
}) {
  // El listener de Esc solo vive mientras el modal está abierto (Regla de Hooks:
  // el hook va SIEMPRE antes de cualquier return).
  useEffect(() => {
    if (!abierto) return
    const alPresionar = e => { if (e.key === 'Escape') onCerrar?.() }
    window.addEventListener('keydown', alPresionar)
    return () => window.removeEventListener('keydown', alPresionar)
  }, [abierto, onCerrar])

  if (!abierto) return null

  const { Icono, borde, icono, titulo: colorTitulo } = VARIANTES[variante] ?? VARIANTES.info

  // Sin `acciones` explícitas → un único botón "Entendido" (compatibilidad ModalMensaje).
  const botones = acciones ?? [{ texto: 'Entendido', estilo: 'primario', onClick: onCerrar }]

  // El foco inicial va al botón recomendado (primario); si no hay, al último.
  const idxPrimario = botones.findIndex(b => b.estilo === 'primario')
  const idxFoco = idxPrimario === -1 ? botones.length - 1 : idxPrimario

  // Cuerpo de texto plano: se parte en líneas para decidir entre viñetas o párrafo.
  const lineas = Array.isArray(mensaje)
    ? mensaje.filter(Boolean)
    : (mensaje ?? '').split('\n').filter(Boolean)

  return (
    // Clic en el fondo cierra; clic dentro de la tarjeta no burbujea (stopPropagation).
    <div
      onClick={onCerrar}
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
    >
      <div
        onClick={e => e.stopPropagation()}
        className={`bg-white rounded-lg shadow-xl border border-gray-200 border-t-4 ${borde} p-6 max-w-md w-full mx-4`}
      >
        <div className="flex items-start gap-3 mb-4">
          <Icono className={`${icono} shrink-0 mt-0.5`} size={22} />
          <h3 className={`text-sm font-semibold ${colorTitulo}`}>{titulo}</h3>
        </div>

        {children ? (
          <div className="text-sm text-gray-700 mb-5">{children}</div>
        ) : lineas.length > 1 ? (
          <ul className="list-disc pl-5 space-y-1 text-sm text-gray-700 mb-5">
            {lineas.map((linea, i) => <li key={i}>{linea}</li>)}
          </ul>
        ) : (
          <p className="text-sm text-gray-700 mb-5">{lineas[0] ?? ''}</p>
        )}

        {/* Por defecto los botones van en fila (salida a la izquierda, acción
            principal a la derecha). Con `apilarBotones` van en columna a lo ancho,
            respetando el orden del array `acciones` (primero arriba). */}
        <div className={apilarBotones ? 'flex flex-col gap-2' : 'flex justify-end gap-3'}>
          {botones.map((b, i) => (
            <button
              key={i}
              autoFocus={i === idxFoco}
              onClick={b.onClick}
              disabled={b.deshabilitado}
              className={`px-4 py-2 text-sm font-medium rounded disabled:opacity-60 ${apilarBotones ? 'w-full' : ''} ${ESTILOS_BOTON[b.estilo] ?? ESTILOS_BOTON.primario}`}
            >
              {b.texto}
            </button>
          ))}
        </div>

        {nota && <p className="text-xs text-gray-400 text-center mt-4">{nota}</p>}
      </div>
    </div>
  )
}

export default ModalBase
