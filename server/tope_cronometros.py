"""Topes del cronómetro de producción: cuándo deja de ser creíble y cuándo
lleva demasiado tiempo pausado.

Fuera de cumplimiento.py a propósito: ese módulo responde «¿cumplió?», juicio
de negocio que alimenta informes. Esto es una guarda sobre la captura del dato.
"""
from django.utils import timezone

from .models import RegistroTurnoDia

MARGEN_MINUTOS = 60
TOPE_RESERVA_MINUTOS = 600
PAUSA_ABANDONADA_MINUTOS = 120
AVISO_PAUSA_MINUTOS = 90
AVISOS_FIN_JORNADA_MINUTOS = (45, 30)


def duracion_jornada(cronometro):
    planeacion = cronometro.registro_produccion.registro_planeacion
    if not planeacion.turno or not planeacion.fecha_planeacion:
        return None

    turno_dia = RegistroTurnoDia.objects.filter(
        turno=planeacion.turno, fecha=planeacion.fecha_planeacion
    ).first()
    return turno_dia.minutos_totales if turno_dia else None


def tope_minutos(duracion):
    if duracion is None:
        return TOPE_RESERVA_MINUTOS
    return duracion + MARGEN_MINUTOS


def minutos_medidos(cronometro, ahora=None):
    ahora = ahora or timezone.now()
    transcurridos = (ahora - cronometro.inicio).total_seconds()

    # total_segundos_pausados solo acumula al reanudar: la pausa abierta no
    # está en ningún acumulador.
    abierta = cronometro.pausas.filter(fin_pausa__isnull=True).first()
    en_pausa = (ahora - abierta.inicio_pausa).total_seconds() if abierta else 0

    return (transcurridos - cronometro.total_segundos_pausados - en_pausa) / 60


def techo_excedido(neto, tope):
    return neto > tope


def minutos_en_pausa(cronometro, ahora=None):
    abierta = cronometro.pausas.filter(fin_pausa__isnull=True).first()
    if abierta is None:
        return None

    ahora = ahora or timezone.now()
    return (ahora - abierta.inicio_pausa).total_seconds() / 60


def pausa_abandonada(minutos_pausa):
    return minutos_pausa is not None and minutos_pausa > PAUSA_ABANDONADA_MINUTOS
