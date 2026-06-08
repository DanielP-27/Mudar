// src/api/dashboard.js
import api from './axios'

// Retorna las métricas globales del sistema para el dashboard principal
export const obtenerDashboard = () =>
  api.get('/api/dashboard/')