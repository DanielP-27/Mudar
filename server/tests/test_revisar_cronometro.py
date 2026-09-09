"""Marcar un cierre automático como atendido, y que salga de la franja.

Antes de esto, la sección de cerrados sólo se vaciaba cuando expiraba su ventana de 48
horas: nada distinguía el cronómetro que alguien ya miró del que nadie ha visto. La marca
es la segunda salida de esa sección, y estas pruebas son las que impiden que se pierda.

GERENCIA está DENEGADA aquí y autorizada en la vista de avisos. No es un descuido: aquélla
lee y ésta escribe, y el permiso se comprueba por operación y no por recurso.

Las dos listas de roles se escriben a mano y NO se importan de la vista. Si se importaran,
la suite compararía el código consigo mismo y pasaría siempre.
"""
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import SimpleTestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from server.models import (
    AuditoriaDom,
    Cliente,
    Dom,
    PerfilUsuario,
    RegistroPlaneacion,
    RegistroProduccion,
    RegistroTiempoProduccion,
    RegistroTurnoDia,
    Turno,
)

ROLES_AUTORIZADOS = {'ADMIN', 'LIDER_PLANTA'}
ROLES_DENEGADOS = {'GERENCIA', 'PLANEADOR', 'ANALISTA_1', 'ANALISTA_2'}

# Valor centinela para minutos_asignados: no coincide con los minutos de ningún
# cronómetro de esta suite, así que si reaparece sobrescrito se sabe quién lo escribió.
MINUTOS_CENTINELA = 999


class CoberturaDeRolesTests(SimpleTestCase):
    """Un rol nuevo no se anuncia solo: verificar_rol lo deniega por omisión, así que sin
    esta prueba entraría al sistema sin que nadie decidiera si puede marcar revisado."""

    def test_todo_rol_declarado_esta_clasificado(self):
        clasificados = ROLES_AUTORIZADOS | ROLES_DENEGADOS
        for rol, etiqueta in PerfilUsuario.ROLES_CHOICES:
            self.assertIn(rol, clasificados, f'{etiqueta} no está clasificado en esta suite')


class BaseRevisar(APITestCase):
    """Escenario común: un cronómetro que el sistema cerró y que nadie ha revisado.

    Sin pruebas propias, para que las clases que heredan no ejecuten las de la otra."""

    def setUp(self):
        self.usuario = User.objects.create_user(username='lider.revisor', password='X7k#pL2mQ9')
        PerfilUsuario.objects.create(user=self.usuario, rol='LIDER_PLANTA')
        self.client = APIClient()
        self.client.force_authenticate(user=self.usuario)

        self.url = reverse('cronometro-revisar')
        self.url_avisos = reverse('cronometro-avisos')

        self.hoy = timezone.localdate()
        # turno_id explícito: HORAS_SALIDA se indexa por (turno, jornada).
        self.turno = Turno.objects.create(turno_id=1, nombre_turno='Turno de prueba')
        RegistroTurnoDia.objects.create(
            turno=self.turno, fecha=self.hoy, numero_operarios=6, minutos_totales=540,
        )
        cliente = Cliente.objects.create(nombre_cliente='Cliente de prueba')
        self.dom = Dom.objects.create(
            nombre_cliente=cliente,
            tipo_estado_dom='PRODUCCION',
            fecha_solicitada_cliente=self.hoy + timedelta(days=30),
            responsable='Responsable de prueba',
        )
        self.cronometro = self._cronometro(numero=1, cerrado_por_el_sistema=True)

    def _cronometro(self, numero, cerrado_por_el_sistema):
        """Un cronómetro ya finalizado. cerrado_por_sistema nulo = lo cerró una persona."""
        planeacion = RegistroPlaneacion.objects.create(
            dom=self.dom, numero_registro=numero,
            turno=self.turno, fecha_planeacion=self.hoy,
        )
        self.produccion = RegistroProduccion.objects.create(
            registro_planeacion=planeacion, numero_registro=numero,
        )
        ahora = timezone.now()
        return RegistroTiempoProduccion.objects.create(
            registro_produccion=self.produccion,
            estado='FINALIZADO',
            inicio=ahora - timedelta(hours=10),
            fin=ahora - timedelta(hours=1),
            minutos_totales=540,
            usuario=self.usuario,
            cerrado_por_sistema=ahora - timedelta(hours=1) if cerrado_por_el_sistema else None,
            motivo_cierre=RegistroTiempoProduccion.MOTIVO_TECHO if cerrado_por_el_sistema else None,
        )

    def _revisar(self, cronometro_id=None):
        return self.client.post(
            self.url, {'cronometro_id': cronometro_id or self.cronometro.id}, format='json'
        )

    def _ids_cerrados(self):
        respuesta = self.client.get(self.url_avisos)
        return [renglon['id'] for renglon in respuesta.data['cerrados_recientes']]


class RevisarPermisosTests(BaseRevisar):

    def _cliente_con_rol(self, rol):
        usuario = User.objects.create_user(username='usuario.%s' % rol.lower(), password='X7k#pL2mQ9')
        PerfilUsuario.objects.create(user=usuario, rol=rol)
        cliente = APIClient()
        cliente.force_authenticate(user=usuario)
        return cliente

    def test_los_roles_que_actuan_sobre_la_planta_pueden_revisar(self):
        for rol in ROLES_AUTORIZADOS:
            with self.subTest(rol=rol):
                # Uno por rol: el segundo encontraría el cronómetro ya revisado.
                cronometro = self._cronometro(numero=100 + len(rol), cerrado_por_el_sistema=True)
                respuesta = self._cliente_con_rol(rol).post(
                    self.url, {'cronometro_id': cronometro.id}, format='json'
                )
                self.assertEqual(respuesta.status_code, status.HTTP_200_OK)

    def test_gerencia_ve_la_franja_pero_no_puede_marcar(self):
        """La distinción que separa esta vista de la de avisos: aquélla lee, ésta escribe."""
        respuesta = self._cliente_con_rol('GERENCIA').post(
            self.url, {'cronometro_id': self.cronometro.id}, format='json'
        )

        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)
        self.cronometro.refresh_from_db()
        self.assertIsNone(self.cronometro.revisado_en)

    def test_los_roles_sin_relacion_con_planta_reciben_403(self):
        for rol in ROLES_DENEGADOS:
            with self.subTest(rol=rol):
                respuesta = self._cliente_con_rol(rol).post(
                    self.url, {'cronometro_id': self.cronometro.id}, format='json'
                )
                self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)

    def test_sin_autenticar_no_llega_a_la_guarda_de_rol(self):
        respuesta = APIClient().post(self.url, {'cronometro_id': self.cronometro.id}, format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_401_UNAUTHORIZED)


class RevisarEfectoTests(BaseRevisar):
    """Qué cambia y qué NO cambia al marcar un cronómetro como revisado."""

    def test_el_revisado_desaparece_de_la_franja(self):
        self.assertIn(self.cronometro.id, self._ids_cerrados())

        self._revisar()

        self.assertNotIn(self.cronometro.id, self._ids_cerrados())

    def test_persiste_quien_lo_revisó_y_cuándo(self):
        """Los dos campos, no sólo el que filtra: una revisión sin autor no dice nada."""
        self._revisar()

        self.cronometro.refresh_from_db()
        self.assertIsNotNone(self.cronometro.revisado_en)
        self.assertEqual(self.cronometro.revisado_por, self.usuario)

    def test_no_toca_los_minutos_del_registro_de_producción(self):
        """La razón de que la vista use update() y no save().

        El save() de RegistroTiempoProduccion propaga minutos_totales al registro de
        producción en cada guardado de un cronómetro finalizado. Marcar «revisado» no debe
        escribir en otra tabla, y esta prueba es lo único que lo impide en un refactor."""
        RegistroProduccion.objects.filter(pk=self.produccion.pk).update(
            minutos_asignados=MINUTOS_CENTINELA
        )

        self._revisar()

        self.produccion.refresh_from_db()
        self.assertEqual(self.produccion.minutos_asignados, MINUTOS_CENTINELA)

    def test_no_altera_los_minutos_del_propio_cronómetro(self):
        """Revisar declara que alguien se hizo cargo; no corrige el dato impuesto. Eso es
        la segunda mitad de la resolución humana y todavía no existe."""
        self._revisar()

        self.cronometro.refresh_from_db()
        self.assertEqual(self.cronometro.minutos_totales, 540)
        self.assertEqual(self.cronometro.estado, 'FINALIZADO')

    def test_deja_una_fila_de_auditoría(self):
        self._revisar()

        filas = AuditoriaDom.objects.filter(dom=self.dom, accion='EDICION')
        self.assertEqual(filas.count(), 1)
        self.assertEqual(filas.first().usuario, self.usuario)
        self.assertEqual(filas.first().etapa, 'etapa_4')
        self.assertIn('revisado_en', filas.first().campos_modificados)


class RevisarGuardasTests(BaseRevisar):

    def test_es_idempotente_y_no_duplica_la_auditoría(self):
        """El filtro por revisado_en nulo va dentro del update, así que el segundo intento
        actualiza cero filas: ni reescribe la marca ni añade una fila más."""
        self._revisar()
        self.cronometro.refresh_from_db()
        primera_marca = self.cronometro.revisado_en

        segunda = self._revisar()

        self.assertEqual(segunda.status_code, status.HTTP_200_OK)
        self.cronometro.refresh_from_db()
        self.assertEqual(self.cronometro.revisado_en, primera_marca)
        self.assertEqual(AuditoriaDom.objects.filter(dom=self.dom, accion='EDICION').count(), 1)

    def test_un_cierre_humano_no_se_revisa(self):
        """cerrado_por_sistema nulo significa que lo cerró una persona: no impuso ningún
        dato, así que no hay nada que atender."""
        humano = self._cronometro(numero=2, cerrado_por_el_sistema=False)

        respuesta = self._revisar(cronometro_id=humano.id)

        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
        humano.refresh_from_db()
        self.assertIsNone(humano.revisado_en)
        self.assertEqual(AuditoriaDom.objects.count(), 0)

    def test_sin_cronometro_id_responde_400(self):
        respuesta = self.client.post(self.url, {}, format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_un_cronometro_inexistente_responde_404(self):
        respuesta = self._revisar(cronometro_id=999999)
        self.assertEqual(respuesta.status_code, status.HTTP_404_NOT_FOUND)

    def test_un_cronometro_id_no_numérico_responde_404_y_no_revienta(self):
        """La conversión falla antes de consultar, así que nunca se lanza DoesNotExist."""
        respuesta = self._revisar(cronometro_id='abc')
        self.assertEqual(respuesta.status_code, status.HTTP_404_NOT_FOUND)
