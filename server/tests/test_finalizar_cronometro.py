"""Por qué no se puede finalizar un cronómetro, que son tres razones y no una.

Hasta ahora las tres respondían lo mismo: «No se puede finalizar un cronometro en estado
FINALIZADO». La que más importa es la que quedaba invisible — cuando el cierre lo hizo el
sistema, los minutos guardados son el tope impuesto y no lo que se trabajó, y el líder se
iba creyendo que su producción quedó registrada con su duración real.

Dos niveles, y el segundo no es redundante:

  1. La regla — _rechazo_al_finalizar, sin base de datos ni cliente HTTP.
  2. El cableado — que la vista la llame de verdad y siga finalizando lo que sí procede.
"""
from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from server import views
from server.models import (
    Cliente,
    Dom,
    PerfilUsuario,
    RegistroPlaneacion,
    RegistroProduccion,
    RegistroTiempoProduccion,
    Turno,
)

URL_FINALIZAR = '/api/cronometro/finalizar/'


class RechazoAlFinalizarTests(SimpleTestCase):
    """La regla sola. Los objetos se arman en memoria y nada se guarda."""

    MOMENTO = timezone.make_aware(datetime(2026, 8, 25, 14, 7))

    def _cronometro(self, **campos):
        return RegistroTiempoProduccion(inicio=self.MOMENTO - timedelta(hours=8), **campos)

    def test_el_que_esta_en_curso_no_se_rechaza(self):
        self.assertIsNone(views._rechazo_al_finalizar(self._cronometro(estado='EN_CURSO')))

    def test_el_cerrado_por_el_sistema_dice_que_fue_el_sistema(self):
        cronometro = self._cronometro(
            estado='FINALIZADO', fin=self.MOMENTO, cerrado_por_sistema=self.MOMENTO,
            motivo_cierre=RegistroTiempoProduccion.MOTIVO_TECHO,
        )

        mensaje = views._rechazo_al_finalizar(cronometro)

        self.assertIn('El sistema cerró este cronómetro', mensaje)
        self.assertIn('25/08/2026 14:07', mensaje)
        self.assertIn('Superó el tope de la jornada', mensaje)
        self.assertIn('no los medidos', mensaje)

    def test_el_cerrado_por_pausa_abandonada_nombra_ese_motivo(self):
        """La etiqueta sale de MOTIVOS_CIERRE: no hay una segunda lista de textos."""
        cronometro = self._cronometro(
            estado='FINALIZADO', fin=self.MOMENTO, cerrado_por_sistema=self.MOMENTO,
            motivo_cierre=RegistroTiempoProduccion.MOTIVO_PAUSA,
        )

        self.assertIn('Pausa abandonada', views._rechazo_al_finalizar(cronometro))

    def test_el_cerrado_por_una_persona_no_menciona_al_sistema(self):
        cronometro = self._cronometro(estado='FINALIZADO', fin=self.MOMENTO)

        mensaje = views._rechazo_al_finalizar(cronometro)

        self.assertIn('ya fue finalizado', mensaje)
        self.assertIn('25/08/2026 14:07', mensaje)
        self.assertNotIn('sistema', mensaje)

    def test_el_pausado_dice_que_hacer_y_no_como_se_llama_su_estado(self):
        mensaje = views._rechazo_al_finalizar(self._cronometro(estado='PAUSADO'))

        self.assertEqual(mensaje, 'Reanude el cronómetro antes de finalizarlo.')
        self.assertNotIn('PAUSADO', mensaje)

    def test_el_cierre_del_sistema_gana_sobre_el_generico(self):
        """Un cerrado por el sistema también está FINALIZADO: si el orden se invirtiera,
        la segunda guarda lo atraparía y el mensaje que importa no llegaría nunca."""
        cronometro = self._cronometro(
            estado='FINALIZADO', fin=self.MOMENTO, cerrado_por_sistema=self.MOMENTO,
            motivo_cierre=RegistroTiempoProduccion.MOTIVO_TECHO,
        )

        self.assertNotIn('ya fue finalizado', views._rechazo_al_finalizar(cronometro))


class FinalizarPorEndpointTests(APITestCase):
    """El cableado: que la vista use la regla y que el camino correcto siga abierto."""

    def setUp(self):
        self.usuario = User.objects.create_user(username='lider.fin', password='X7k#pL2mQ9')
        PerfilUsuario.objects.create(user=self.usuario, rol='LIDER_PLANTA')
        self.client = APIClient()
        self.client.force_authenticate(user=self.usuario)

        turno = Turno.objects.create(turno_id=1, nombre_turno='Turno de prueba')
        cliente = Cliente.objects.create(nombre_cliente='Cliente de prueba')
        hoy = timezone.localdate()
        dom = Dom.objects.create(
            nombre_cliente=cliente,
            tipo_estado_dom='PRODUCCION',
            fecha_solicitada_cliente=hoy + timedelta(days=30),
            responsable='Responsable de prueba',
        )
        planeacion = RegistroPlaneacion.objects.create(
            dom=dom, numero_registro=1, turno=turno, fecha_planeacion=hoy,
        )
        produccion = RegistroProduccion.objects.create(
            registro_planeacion=planeacion, numero_registro=1,
        )
        self.cronometro = RegistroTiempoProduccion.objects.create(
            registro_produccion=produccion, estado='EN_CURSO',
            inicio=timezone.now() - timedelta(minutes=90), usuario=self.usuario,
        )

    def _finalizar(self):
        return self.client.post(URL_FINALIZAR, {'cronometro_id': self.cronometro.id})

    def test_el_flujo_correcto_sigue_finalizando(self):
        respuesta = self._finalizar()

        self.cronometro.refresh_from_db()
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertEqual(self.cronometro.estado, 'FINALIZADO')
        self.assertIsNone(self.cronometro.cerrado_por_sistema)

    def test_el_cerrado_por_el_sistema_recibe_su_mensaje(self):
        self.cronometro.estado = 'FINALIZADO'
        self.cronometro.fin = timezone.now()
        self.cronometro.cerrado_por_sistema = timezone.now()
        self.cronometro.motivo_cierre = RegistroTiempoProduccion.MOTIVO_TECHO
        self.cronometro.save()

        respuesta = self._finalizar()

        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('El sistema cerró este cronómetro', respuesta.data['error'])

    def test_el_pausado_recibe_el_suyo(self):
        self.cronometro.estado = 'PAUSADO'
        self.cronometro.save()

        respuesta = self._finalizar()

        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(respuesta.data['error'],
                         'Reanude el cronómetro antes de finalizarlo.')
