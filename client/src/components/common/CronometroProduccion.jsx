// src/components/common/CronometroProduccion.jsx
import { useState, useEffect } from 'react'
import { FiPlay, FiPause, FiSquare, FiClock } from 'react-icons/fi'
import {
  iniciarCronometro,
  pausarCronometro,
  reanudarCronometro,
  finalizarCronometro,
} from '../../api/cronometro'
import { extraerMensajeError } from '../../utils/errores'
import { useAvisos } from '../../context/AvisosContext'

const formatearTiempo = (segundos) => {
  const h = Math.floor(segundos / 3600)
  const m = Math.floor((segundos % 3600) / 60)
  const s = segundos % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

function CronometroProduccion({ registrosTiempo = [], registroProduccionId, onAccion, puedeOperar = false, personasAsignadas }) {
  // Se refresca en el finally y no sólo al acertar: si finalizar falla porque el sistema
  // ya lo cerró, la franja debe reflejar ese cambio igual. Sin esto, quien cierra un
  // cronómetro y se queda en la pantalla seguiría viendo su propio aviso.
  const { refrescar } = useAvisos()

  const cronometroActivo =
    registrosTiempo.find(r => r.estado === 'EN_CURSO' || r.estado === 'PAUSADO') ??
    registrosTiempo.reduce((mas, r) =>
      r.estado === 'FINALIZADO' && (!mas || r.id > mas.id) ? r : mas, null)

  const [segundosTranscurridos, setSegundosTranscurridos] = useState(0)
  const [ejecutando, setEjecutando]                       = useState(false)
  const [error, setError]                                 = useState(null)

  // Contador en tiempo real — solo corre cuando el cronómetro está EN_CURSO
  useEffect(() => {
    if (cronometroActivo?.estado !== 'EN_CURSO') return

    const calcular = () => {
      const inicio  = new Date(cronometroActivo.inicio).getTime() / 1000
      const ahora   = Date.now() / 1000
      const elapsed = ahora - inicio - (cronometroActivo.total_segundos_pausados ?? 0)
      setSegundosTranscurridos(Math.max(0, Math.floor(elapsed)))
    }

    calcular()
    const intervalo = setInterval(calcular, 1000)
    return () => clearInterval(intervalo)
  }, [cronometroActivo?.estado, cronometroActivo?.inicio, cronometroActivo?.total_segundos_pausados])

  // Calcula el tiempo acumulado en el momento exacto en que se pausó
  const tiempoAlPausar = () => {
    const pausaActiva = cronometroActivo?.pausas?.find(p => !p.fin_pausa)
    if (!pausaActiva) return segundosTranscurridos
    const inicio      = new Date(cronometroActivo.inicio).getTime() / 1000
    const inicioPausa = new Date(pausaActiva.inicio_pausa).getTime() / 1000
    return Math.max(0, Math.floor(inicioPausa - inicio - (cronometroActivo.total_segundos_pausados ?? 0)))
  }

  const alIniciar = async () => {
    setEjecutando(true)
    setError(null)
    try {
      await iniciarCronometro(registroProduccionId)
      await onAccion()
    } catch (err) {
      setError(extraerMensajeError(err, 'No se pudo iniciar el cronómetro.'))
    } finally {
      setEjecutando(false)
      refrescar()
    }
  }

  const alPausar = async () => {
    setEjecutando(true)
    setError(null)
    try {
      await pausarCronometro(cronometroActivo.id)
      await onAccion()
    } catch (err) {
      setError(extraerMensajeError(err, 'No se pudo pausar el cronómetro.'))
    } finally {
      setEjecutando(false)
      refrescar()
    }
  }

  const alReanudar = async () => {
    setEjecutando(true)
    setError(null)
    try {
      await reanudarCronometro(cronometroActivo.id)
      await onAccion()
    } catch (err) {
      setError(extraerMensajeError(err, 'No se pudo reanudar el cronómetro.'))
    } finally {
      setEjecutando(false)
      refrescar()
    }
  }

  const alFinalizar = async () => {
    setEjecutando(true)
    setError(null)
    try {
      await finalizarCronometro(cronometroActivo.id)
      await onAccion()
    } catch (err) {
      setError(extraerMensajeError(err, 'No se pudo finalizar el cronómetro.'))
    } finally {
      setEjecutando(false)
      refrescar()
    }
  }

  const btnBase = 'flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded disabled:opacity-50'

  return (
    <div className="border border-gray-200 rounded-lg p-4 bg-gray-50 space-y-3">

      <div className="flex items-center gap-2">
        <FiClock size={14} className="text-gray-500" />
        <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
          Cronómetro de producción
        </p>
      </div>

      {/* Estado 1 — Sin cronómetro */}
      {!cronometroActivo && (
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-sm text-gray-500">Sin registro de tiempo iniciado.</p>
            {puedeOperar && !personasAsignadas && (
              <p className="text-sm font-semibold text-amber-600 mt-1">
                Ingrese el número de personas asignadas antes de iniciar el cronómetro.
              </p>
            )}
          </div>
          {puedeOperar && (
            <button onClick={alIniciar} disabled={ejecutando || !personasAsignadas}
              className={`${btnBase} bg-[#1A56A0] text-white hover:bg-[#134080]`}>
              <FiPlay size={12} /> Iniciar
            </button>
          )}
        </div>
      )}

      {/* Estado 2 — EN_CURSO */}
      {cronometroActivo?.estado === 'EN_CURSO' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">
              En curso
            </span>
            <span className="text-2xl font-mono font-semibold text-gray-800">
              {formatearTiempo(segundosTranscurridos)}
            </span>
          </div>
          {puedeOperar && (
            <div className="flex gap-2 justify-end">
              <button onClick={alPausar} disabled={ejecutando}
                className={`${btnBase} bg-amber-500 text-white hover:bg-amber-600`}>
                <FiPause size={12} /> Pausar
              </button>
              <button onClick={alFinalizar} disabled={ejecutando}
                className={`${btnBase} bg-red-600 text-white hover:bg-red-700`}>
                <FiSquare size={12} /> Finalizar
              </button>
            </div>
          )}
        </div>
      )}

      {/* Estado 3 — PAUSADO */}
      {cronometroActivo?.estado === 'PAUSADO' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-700">
              Pausado
            </span>
            <span className="text-2xl font-mono font-semibold text-gray-400">
              {formatearTiempo(tiempoAlPausar())}
            </span>
          </div>
          {puedeOperar && (
            <div className="flex gap-2 justify-end">
              <button onClick={alReanudar} disabled={ejecutando}
                className={`${btnBase} bg-[#1A56A0] text-white hover:bg-[#134080]`}>
                <FiPlay size={12} /> Reanudar
              </button>
              <button onClick={alFinalizar} disabled={ejecutando}
                className={`${btnBase} bg-red-600 text-white hover:bg-red-700`}>
                <FiSquare size={12} /> Finalizar
              </button>
            </div>
          )}
        </div>
      )}

      {/* Estado 4 — FINALIZADO */}
      {cronometroActivo?.estado === 'FINALIZADO' && (
        <div className="flex items-center justify-between">
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
            Finalizado
          </span>
          <p className="text-sm text-gray-700">
            Tiempo registrado:{' '}
            <span className="font-semibold">{cronometroActivo.minutos_totales} min</span>
          </p>
        </div>
      )}

      {/* Error inline */}
      {error && (
        <p className="text-xs text-red-600">{error}</p>
      )}

    </div>
  )
}

export default CronometroProduccion
