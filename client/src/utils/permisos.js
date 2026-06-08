// src/utils/permisos.js

// Mapa de permisos por etapa según rol — replica puede_editar_etapas() de models.py
const PERMISOS_ETAPAS = {
  GERENCIA:     [],
  ADMIN:        ['etapa_0', 'etapa_1', 'etapa_2', 'etapa_3', 'etapa_4', 'etapa_5', 'etapa_6'],
  ANALISTA_1:   ['etapa_0', 'etapa_1', 'etapa_6'],
  ANALISTA_2:   ['etapa_0', 'etapa_1', 'etapa_6'],
  PLANEADOR:    ['etapa_2'],
  LIDER_PLANTA: ['etapa_3', 'etapa_4', 'etapa_5'],
}

// Verifica si un rol puede editar una etapa específica
export const puedeEditarEtapa = (rol, etapa) =>
  PERMISOS_ETAPAS[rol]?.includes(etapa) ?? false

// Retorna todas las etapas editables para un rol dado
export const etapasEditables = (rol) =>
  PERMISOS_ETAPAS[rol] ?? []

// Verifica si un rol tiene acceso de solo lectura (ninguna etapa editable)
export const esSoloLectura = (rol) =>
  (PERMISOS_ETAPAS[rol]?.length ?? 0) === 0