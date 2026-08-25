"""Cronómetro de producción: cuándo el sistema debe cerrarlo y cuándo hay que
avisar de él. Los topes del cierre automático y los umbrales de la franja.

Fuera de cumplimiento.py a propósito: ese módulo responde «¿cumplió?», juicio
de negocio que alimenta informes. Esto es una guarda sobre la captura del dato.
"""
from datetime import datetime, time, timedelta

from django.utils import timezone

from .models import RegistroTiempoProduccion, RegistroTurnoDia

MARGEN_MINUTOS = 60
TOPE_RESERVA_MINUTOS = 600
PAUSA_ABANDONADA_MINUTOS = 120
AVISO_PAUSA_MINUTOS = 90
AVISO_FIN_JORNADA_MINUTOS = 45

# Hora a la que sale cada turno, por (turno_id, jornada). Confirmada con el cliente
# el 2026-08-25. Turno mañana = 1, turno tarde = 3; el catálogo no tiene un 2.
# Un turno nuevo no se anuncia solo: sin su entrada aquí, sus cronómetros salen en
# la franja sin ninguna marca de turno y nada lo señala.
HORAS_SALIDA = {
    (1, 510): time(14, 30),
    (1, 540): time(16, 0),
    (3, 420): time(19, 0),
    (3, 480): time(14, 0),
    (3, 540): time(19, 0),
}


# --- Resolución: las dos únicas funciones que tocan la base ---

def turno_dia_de(cronometro):
    planeacion = cronometro.registro_produccion.registro_planeacion
    if not planeacion.turno or not planeacion.fecha_planeacion:
        return None

    return RegistroTurnoDia.objects.filter(
        turno=planeacion.turno, fecha=planeacion.fecha_planeacion
    ).first()


def pausa_abierta_de(cronometro):
    return cronometro.pausas.filter(fin_pausa__isnull=True).first()


# --- Cálculo: reciben lo resuelto y no consultan nada ---

def duracion_jornada(turno_dia):
    return turno_dia.minutos_totales if turno_dia else None


def hora_salida(turno_dia):
    if turno_dia is None:
        return None

    hora = HORAS_SALIDA.get((turno_dia.turno_id, turno_dia.minutos_totales))
    if hora is None:
        return None

    return timezone.make_aware(datetime.combine(turno_dia.fecha, hora))


def tope_minutos(duracion):
    if duracion is None:
        return TOPE_RESERVA_MINUTOS
    return duracion + MARGEN_MINUTOS


def minutos_medidos(cronometro, pausa_abierta, ahora=None):
    ahora = ahora or timezone.now()
    transcurridos = (ahora - cronometro.inicio).total_seconds()

    # total_segundos_pausados solo acumula al reanudar: la pausa abierta no
    # está en ningún acumulador.
    en_pausa = (ahora - pausa_abierta.inicio_pausa).total_seconds() if pausa_abierta else 0

    return (transcurridos - cronometro.total_segundos_pausados - en_pausa) / 60


def techo_excedido(neto, tope):
    return neto > tope


def minutos_en_pausa(pausa_abierta, ahora=None):
    if pausa_abierta is None:
        return None

    ahora = ahora or timezone.now()
    return (ahora - pausa_abierta.inicio_pausa).total_seconds() / 60


def pausa_abandonada(minutos_pausa):
    return minutos_pausa is not None and minutos_pausa > PAUSA_ABANDONADA_MINUTOS


def pausa_larga(minutos_pausa):
    return minutos_pausa is not None and minutos_pausa > AVISO_PAUSA_MINUTOS


def por_terminar(salida, ahora=None):
    if salida is None:
        return False

    faltan = (salida - (ahora or timezone.now())).total_seconds() / 60
    return 0 < faltan <= AVISO_FIN_JORNADA_MINUTOS


# No se llama «vencido»: en este proyecto un DOM vencido es otro hecho —se le pasó la
# fecha de entrega— y el techo del cierre automático es un tercero, sobre tiempo neto.
# Esto sólo dice que el turno de esa planeación ya salió, por reloj de pared.
def turno_terminado(salida, ahora=None):
    if salida is None:
        return False

    return salida < (ahora or timezone.now())


def decidir_cierre(cronometro, turno_dia, pausa_abierta, ahora=None):
    """(motivo, fin) si el sistema debe cerrarlo; (None, None) si no.

    El techo tiene precedencia: si dispara, la pausa ni se evalúa."""
    tope = tope_minutos(duracion_jornada(turno_dia))

    if techo_excedido(minutos_medidos(cronometro, pausa_abierta, ahora), tope):
        pausado = timedelta(seconds=cronometro.total_segundos_pausados)
        return RegistroTiempoProduccion.MOTIVO_TECHO, cronometro.inicio + timedelta(minutes=tope) + pausado

    if pausa_abandonada(minutos_en_pausa(pausa_abierta, ahora)):
        abandono = timedelta(minutes=PAUSA_ABANDONADA_MINUTOS)
        return RegistroTiempoProduccion.MOTIVO_PAUSA, pausa_abierta.inicio_pausa + abandono

    return None, None
