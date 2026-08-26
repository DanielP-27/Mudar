// src/api/cronometro.js
import api from './axios'

// Inicia un nuevo cronómetro para el registro de producción indicado
export const iniciarCronometro = (registroProduccionId) =>
  api.post('/api/cronometro/iniciar/', { registro_produccion: registroProduccionId })

// Pausa el cronómetro activo indicado
export const pausarCronometro = (cronometroId) =>
  api.post('/api/cronometro/pausar/', { cronometro_id: cronometroId })

// Reanuda el cronómetro pausado indicado
export const reanudarCronometro = (cronometroId) =>
  api.post('/api/cronometro/reanudar/', { cronometro_id: cronometroId })

// Finaliza el cronómetro indicado y registra los minutos totales
export const finalizarCronometro = (cronometroId) =>
  api.post('/api/cronometro/finalizar/', { cronometro_id: cronometroId })

// Lo que la franja necesita: los cronómetros sin finalizar y los que cerró el sistema
// en las últimas 48 horas. Ojo — este GET escribe: el barrido corre antes de listar.
export const consultarAvisos = () =>
  api.get('/api/cronometros/avisos/')

