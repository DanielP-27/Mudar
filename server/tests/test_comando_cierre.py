"""El comando que hace ejecutable el cierre, y su modo de mirar sin tocar.

El escenario se ancla al reloj real y no a una fecha fija, porque el comando lee
timezone.now() por su cuenta: es lo único que decide qué cronómetros encuentra.
"""
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from server.models import (
    Cliente,
    Dom,
    RegistroPlaneacion,
    RegistroProduccion,
    RegistroTiempoProduccion,
    RegistroTurnoDia,
    Turno,
)


class ComandoCierreTests(TestCase):
    """Dos cronómetros abiertos: uno de doce horas, que excede el tope de 600, y otro
    de una hora, que no."""

    def setUp(self):
        self.turno = Turno.objects.create(nombre_turno='Turno de prueba')
        self.cliente = Cliente.objects.create(nombre_cliente='Cliente de prueba')
        self.dom = Dom.objects.create(
            nombre_cliente=self.cliente,
            tipo_estado_dom='PRODUCCION',
            fecha_solicitada_cliente=timezone.localdate() + timedelta(days=30),
            responsable='Responsable de prueba',
        )
        self.planeacion = RegistroPlaneacion.objects.create(
            dom=self.dom, numero_registro=1,
            turno=self.turno, fecha_planeacion=timezone.localdate(),
        )
        RegistroTurnoDia.objects.create(
            turno=self.turno, fecha=timezone.localdate(),
            numero_operarios=6, minutos_totales=540,
        )

        self.olvidado = self._cronometro(numero=1, hace_horas=12)
        self.reciente = self._cronometro(numero=2, hace_horas=1)

    def _cronometro(self, numero, hace_horas):
        produccion = RegistroProduccion.objects.create(
            registro_planeacion=self.planeacion, numero_registro=numero,
        )
        return RegistroTiempoProduccion.objects.create(
            registro_produccion=produccion,
            inicio=timezone.now() - timedelta(hours=hace_horas),
            estado='EN_CURSO',
        )

    def ejecutar(self, *argumentos):
        salida = StringIO()
        call_command('cerrar_cronometros', *argumentos, stdout=salida)
        return salida.getvalue()

    def test_cierra_solo_los_que_superaron_el_tope(self):
        self.ejecutar()

        self.olvidado.refresh_from_db()
        self.reciente.refresh_from_db()
        self.assertEqual(self.olvidado.estado, 'FINALIZADO')
        self.assertEqual(self.olvidado.minutos_totales, 600)
        self.assertEqual(self.reciente.estado, 'EN_CURSO')

    def test_informa_los_conteos(self):
        salida = self.ejecutar()

        self.assertIn(f'Cerrado el cronómetro {self.olvidado.id}', salida)
        self.assertIn('TECHO_JORNADA', salida)
        self.assertIn('1 cerrados de 2 abiertos', salida)

    def test_simular_no_escribe_nada(self):
        salida = self.ejecutar('--simular')

        self.olvidado.refresh_from_db()
        self.assertEqual(self.olvidado.estado, 'EN_CURSO')
        self.assertIsNone(self.olvidado.fin)
        self.assertIsNone(self.olvidado.cerrado_por_sistema)
        self.assertIn('No se escribió nada', salida)

    def test_simular_anuncia_lo_mismo_que_haria(self):
        anuncio = self.ejecutar('--simular')
        self.assertIn(f'Cerraría el cronómetro {self.olvidado.id}', anuncio)
        self.assertIn('1 de 2 abiertos', anuncio)

        hecho = self.ejecutar()
        self.assertIn(f'Cerrado el cronómetro {self.olvidado.id}', hecho)
        self.assertIn('1 cerrados de 2 abiertos', hecho)
