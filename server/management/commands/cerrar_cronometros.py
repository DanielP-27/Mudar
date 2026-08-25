"""Cierra los cronómetros que el sistema debe cerrar.

Lo mismo que hará el endpoint de avisos en cada navegación, disponible a mano y
para el cron del servidor. El dato escrito es idéntico venga de donde venga el
disparo, porque el fin se calcula y no se lee del reloj.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from server.cierre_cronometros import barrer
from server.models import RegistroTiempoProduccion
from server.tope_cronometros import decidir_cierre, pausa_abierta_de, turno_dia_de


class Command(BaseCommand):
    help = 'Cierra los cronómetros que superaron el tope de su jornada o llevan demasiado en pausa.'

    def add_arguments(self, parser):
        parser.add_argument('--simular', action='store_true',
                            help='Muestra qué cerraría, sin escribir nada.')

    def handle(self, *args, **opciones):
        # Un solo instante para toda la pasada: si cada función leyera el reloj por
        # su cuenta, dos cronómetros de la misma corrida se medirían con relojes distintos.
        ahora = timezone.now()

        abiertos = (RegistroTiempoProduccion.objects
                    .exclude(estado='FINALIZADO')
                    .select_related('registro_produccion__registro_planeacion__dom'))

        candidatos = [(c, turno_dia_de(c), pausa_abierta_de(c)) for c in abiertos]

        if opciones['simular']:
            return self._simular(candidatos, ahora)

        cerrados = barrer(candidatos, ahora)
        for cronometro, motivo in cerrados:
            self.stdout.write(f'Cerrado el cronómetro {cronometro.id} — {motivo}')

        self.stdout.write(self.style.SUCCESS(
            f'{len(cerrados)} cerrados de {len(candidatos)} abiertos'))

    def _simular(self, candidatos, ahora):
        # decidir_cierre es cálculo puro: no abre transacción ni escribe.
        procedentes = 0

        for cronometro, turno_dia, pausa_abierta in candidatos:
            motivo, fin = decidir_cierre(cronometro, turno_dia, pausa_abierta, ahora)
            if motivo:
                procedentes += 1
                self.stdout.write(f'Cerraría el cronómetro {cronometro.id} — {motivo} — fin {fin}')

        self.stdout.write(self.style.WARNING(
            f'Simulación: {procedentes} de {len(candidatos)} abiertos. No se escribió nada.'))
