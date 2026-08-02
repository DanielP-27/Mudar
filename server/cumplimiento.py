"""Predicado único de cumplimiento por etapa.

Fuera de views.py a propósito: en las vistas, la regla sólo existe si alguien
abre una pantalla. Aquí queda disponible para informes, migraciones y tareas.

Nadie llama a este módulo todavía. El cableado es la F3.4.
"""

from django.utils import timezone

# PENDIENTE: no hay dato, el tiempo lo resuelve solo.
# ANÓMALO: hay dato pero no es creíble, exige que alguien intervenga.
# Ninguno entra al denominador, pero salen por razones opuestas.
CUMPLIO = 'CUMPLIÓ'
NO_CUMPLIO = 'NO_CUMPLIÓ'
PENDIENTE = 'PENDIENTE'
ANOMALO = 'ANÓMALO'

# Máximas de la experiencia: se escribe el razonamiento, no sólo el número.
# 10 h porque la jornada larga son 9 (540 min) y cada turno abre su propio
# cronómetro. La hora restante es margen para cerrarlo. Confirmado 2026-08-02.
# El mínimo existe porque la implausibilidad tiene dos extremos: 41 h es
# increíble y 6 segundos también.
UMBRAL_MAXIMO_MINUTOS = 10 * 60
UMBRAL_MINIMO_MINUTOS = 1


def _veredicto_booleano(valor):
    # El nulo es PENDIENTE, no incumplimiento. Aquí está el arreglo de fondo:
    # el all() de las vistas trataba el nulo como falso.
    if valor is None:
        return PENDIENTE
    return CUMPLIO if valor else NO_CUMPLIO


def veredicto_almacen(registro_almacen):
    if registro_almacen is None:
        return PENDIENTE
    return _veredicto_booleano(registro_almacen.dom_realizado_planeacion)


def veredicto_produccion(registro_produccion):
    # El declarado por el líder. Es el oficial del porcentaje;
    # cumplimiento_produccion viaja al lado como contraste y no se agrega.
    if registro_produccion is None:
        return PENDIENTE
    return _veredicto_booleano(registro_produccion.segun_planeacion)


def veredicto_tratamiento(registro_tratamiento):
    if registro_tratamiento is None:
        return PENDIENTE
    return _veredicto_booleano(registro_tratamiento.tratamiento_segun_planeacion)


def veredicto_despacho(dom):
    # El único que vive en el DOM y no en un registro hijo.
    if dom is None:
        return PENDIENTE
    return _veredicto_booleano(dom.dom_entregado_ok)


def cronometro_anomalo(cronometro):
    # Vive aquí y no en ESTADO_CHOICES: la anomalía es un juicio, no algo que
    # el usuario haga. Derivado, no almacenado: no necesita tarea programada.
    if cronometro is None:
        return False

    # PAUSADO cuenta: la vista de finalizar exige EN_CURSO (views.py:3658),
    # así que un pausado y olvidado se queda ahí para siempre.
    if cronometro.estado in ('EN_CURSO', 'PAUSADO'):
        if cronometro.inicio is None:
            return True
        minutos = (timezone.now() - cronometro.inicio).total_seconds() / 60
        return minutos > UMBRAL_MAXIMO_MINUTOS

    if cronometro.estado == 'FINALIZADO':
        # Finalizado sin minutos es dato roto, no dato ausente.
        if cronometro.minutos_totales is None:
            return True
        return (cronometro.minutos_totales > UMBRAL_MAXIMO_MINUTOS
                or cronometro.minutos_totales < UMBRAL_MINIMO_MINUTOS)

    return False


def veredicto_tiempo(registro_produccion):
    if registro_produccion is None:
        return PENDIENTE

    cronometros = list(registro_produccion.registros_tiempo.all())

    # La anomalía va PRIMERO: un registro cuyo único cronómetro lleva 15 h
    # corriendo no tiene ninguno finalizado. Sin esto saldría PENDIENTE.
    if any(cronometro_anomalo(c) for c in cronometros):
        return ANOMALO

    finalizados = [c for c in cronometros if c.estado == 'FINALIZADO']
    if not finalizados:
        return PENDIENTE

    # Suma todos los finalizados. minutos_asignados guarda sólo el último;
    # hoy da lo mismo, pero la suma es correcta en los dos escenarios.
    minutos = sum(c.minutos_totales or 0 for c in finalizados)
    personas = registro_produccion.numero_personas_asignadas
    proyectado = registro_produccion.registro_planeacion.tiempo_proyectado

    # Sin personas o sin proyección falta el dato, no hay incumplimiento.
    if not personas or proyectado is None:
        return PENDIENTE

    # Minutos-persona contra minutos-persona.
    return CUMPLIO if minutos * personas <= proyectado else NO_CUMPLIO
