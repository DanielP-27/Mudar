"""Un registro de producción admite un solo cronómetro.

La regla ya vivía en la pantalla —el botón Iniciar no se pinta si existe cualquier
cronómetro—, pero el backend sólo rechazaba los EN_CURSO. Un cronómetro finalizado, o
uno pausado, dejaban abrir otro; y al finalizarlo se perderían los minutos del primero,
porque el modelo asigna y no acumula.

Primera suite del proyecto que ejercita un endpoint HTTP: la regla vive en la vista, no
en el serializer ni en el modelo, así que probarla en otro sitio no probaría nada.
force_authenticate evita montar token y caducidad, que no son lo que está bajo prueba.
"""
from datetime import date

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from server.models import (
    Cliente,
    Dom,
    PerfilUsuario,
    RegistroPlaneacion,
    RegistroProduccion,
    RegistroTiempoProduccion,
)

URL = '/api/cronometro/iniciar/'


class SegundoCronometroTests(APITestCase):

    def setUp(self):
        self.usuario = User.objects.create_user(username='lider.planta', password='X7k#pL2mQ9')
        PerfilUsuario.objects.create(user=self.usuario, rol='LIDER_PLANTA')
        self.client = APIClient()
        self.client.force_authenticate(user=self.usuario)

        self.cliente = Cliente.objects.create(nombre_cliente='Cliente de prueba')
        self.dom = Dom.objects.create(
            nombre_cliente=self.cliente,
            tipo_estado_dom='PRODUCCION',
            fecha_solicitada_cliente=date(2026, 8, 30),
            responsable='Responsable de prueba',
        )
        self.planeacion = RegistroPlaneacion.objects.create(dom=self.dom, numero_registro=1)
        self.produccion = RegistroProduccion.objects.create(
            registro_planeacion=self.planeacion, numero_registro=1,
            numero_personas_asignadas=3,
        )

    def iniciar(self):
        return self.client.post(URL, {'registro_produccion': self.produccion.id}, format='json')

    def cronometro(self, estado, minutos=None):
        return RegistroTiempoProduccion.objects.create(
            registro_produccion=self.produccion,
            inicio=timezone.now(),
            estado=estado,
            minutos_totales=minutos,
        )

    # ------------------------------------------------------------------
    # Los tres estados bloquean
    # ------------------------------------------------------------------

    def test_no_se_puede_iniciar_si_ya_hay_uno_finalizado(self):
        """La deuda: un segundo cronómetro sobrescribiría los minutos del primero."""
        primero = self.cronometro('FINALIZADO', minutos=23)

        respuesta = self.iniciar()

        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            RegistroTiempoProduccion.objects.filter(registro_produccion=self.produccion).count(), 1,
            'Se creó un segundo cronómetro sobre una producción ya cronometrada.'
        )
        primero.refresh_from_db()
        self.assertEqual(primero.minutos_totales, 23)

    def test_no_se_puede_iniciar_si_hay_uno_pausado(self):
        """Un pausado y olvidado tampoco puede quedar sustituido por otro nuevo."""
        self.cronometro('PAUSADO')

        respuesta = self.iniciar()

        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            RegistroTiempoProduccion.objects.filter(registro_produccion=self.produccion).count(), 1
        )

    def test_no_se_puede_iniciar_si_hay_uno_en_curso(self):
        """Comportamiento que ya existía: no perderlo al ampliar la regla."""
        self.cronometro('EN_CURSO')

        respuesta = self.iniciar()

        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            RegistroTiempoProduccion.objects.filter(registro_produccion=self.produccion).count(), 1
        )

    # ------------------------------------------------------------------
    # Control: sin cronómetro, se inicia con normalidad
    # ------------------------------------------------------------------

    def test_sin_cronometro_se_inicia_con_normalidad(self):
        respuesta = self.iniciar()

        self.assertEqual(respuesta.status_code, status.HTTP_201_CREATED, respuesta.data)
        creado = RegistroTiempoProduccion.objects.get(registro_produccion=self.produccion)
        self.assertEqual(creado.estado, 'EN_CURSO')

    def test_el_mensaje_distingue_ya_cronometrado_de_abierto(self):
        """Son dos situaciones distintas para quien las lee: 'alguien lo dejó abierto'
        frente a 'esto ya se midió'."""
        self.cronometro('FINALIZADO', minutos=23)
        finalizado = self.iniciar().data['error']

        RegistroTiempoProduccion.objects.all().delete()
        self.cronometro('EN_CURSO')
        abierto = self.iniciar().data['error']

        self.assertIn('ya fue cronometrada', finalizado)
        self.assertIn('abierto', abierto)
