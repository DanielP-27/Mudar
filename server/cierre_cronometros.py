"""Aplica el cierre automático que decide tope_cronometros.

Módulo aparte porque ese no escribe: allí vive la decisión y aquí la escritura,
con su transacción y su fila de auditoría.
"""
import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .auditoria import registrar_auditoria
from .models import RegistroTiempoProduccion
from .tope_cronometros import PAUSA_ABANDONADA_MINUTOS, decidir_cierre

logger = logging.getLogger(__name__)


def cerrar(cronometro, turno_dia, pausa_abierta, ahora=None):
    """Cierra el cronómetro si procede y devuelve el motivo, o None si no procede."""
    motivo, fin = decidir_cierre(cronometro, turno_dia, pausa_abierta, ahora)
    if motivo is None:
        return None

    with transaction.atomic():
        bloqueado = RegistroTiempoProduccion.objects.select_for_update().get(id=cronometro.id)
        if bloqueado.estado == 'FINALIZADO':
            return None

        if pausa_abierta is not None:
            _cerrar_pausa(bloqueado, pausa_abierta, motivo)

        bloqueado.fin = fin
        bloqueado.estado = 'FINALIZADO'
        bloqueado.cerrado_por_sistema = timezone.now()
        bloqueado.motivo_cierre = motivo
        bloqueado.minutos_totales = bloqueado.calcular_minutos_totales()
        bloqueado.save()

        registrar_auditoria(
            bloqueado.registro_produccion.registro_planeacion.dom,
            None, 'CIERRE_AUTOMATICO', None, etapa='etapa_4',
            campos_modificados={'motivo': motivo, 'minutos_totales': bloqueado.minutos_totales},
        )

    return motivo


def _cerrar_pausa(cronometro, pausa, motivo):
    if motivo == RegistroTiempoProduccion.MOTIVO_TECHO:
        # El fin por techo es anterior a esta pausa: se cierra sin aportar tiempo.
        pausa.fin_pausa = pausa.inicio_pausa
    else:
        pausa.fin_pausa = pausa.inicio_pausa + timedelta(minutes=PAUSA_ABANDONADA_MINUTOS)

    pausa.save()
    cronometro.total_segundos_pausados += pausa.segundos_pausados


def barrer(candidatos, ahora=None):
    """candidatos: iterable de (cronometro, turno_dia, pausa_abierta).

    El fallo de uno no detiene el barrido ni tumba a quien lo disparó."""
    cerrados = []

    for cronometro, turno_dia, pausa_abierta in candidatos:
        try:
            motivo = cerrar(cronometro, turno_dia, pausa_abierta, ahora)
        except Exception:
            logger.exception('No se pudo cerrar el cronómetro %s', cronometro.id)
            continue

        if motivo:
            cerrados.append((cronometro, motivo))

    return cerrados
