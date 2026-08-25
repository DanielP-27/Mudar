"""Quién puede preguntar por los avisos, y qué forma tiene la respuesta.

GERENCIA entra aquí y no en las otras cuatro vistas del cronómetro: aquéllas escriben
y ésta sólo lee. El permiso se comprueba por operación y no por recurso, y esta suite
es lo que impide que esa distinción se pierda en una edición futura.

La forma se fija desde ya, con las listas vacías: quien llene la consulta en el 2.2 no
puede cambiar las claves sin que una prueba lo diga.

Las dos listas de roles se escriben aquí a mano y NO se importan de la vista. Si se
importaran, la suite compararía el código consigo mismo y pasaría siempre.
"""
from datetime import date, datetime, timedelta

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
    PausaTiempoProduccion,
    PerfilUsuario,
    RegistroPlaneacion,
    RegistroProduccion,
    RegistroTiempoProduccion,
    RegistroTurnoDia,
    Turno,
)
from server.tope_cronometros import hora_salida
from server import views

ROLES_AUTORIZADOS = {'ADMIN', 'LIDER_PLANTA', 'GERENCIA'}
ROLES_DENEGADOS = {'PLANEADOR', 'ANALISTA_1', 'ANALISTA_2'}

# Abiertos · sus pausas abiertas · los turnos-día en bloque · los cerrados recientes.
CONSULTAS_DEL_ENDPOINT = 4


class CoberturaDeRolesTests(SimpleTestCase):
    """Un rol nuevo no se anuncia solo: verificar_rol lo deniega por omisión, así que
    sin esta prueba entraría al sistema sin que nadie decidiera si ve la franja."""

    def test_todo_rol_declarado_esta_clasificado(self):
        clasificados = ROLES_AUTORIZADOS | ROLES_DENEGADOS
        for rol, etiqueta in PerfilUsuario.ROLES_CHOICES:
            self.assertIn(rol, clasificados, f'{etiqueta} no está clasificado en esta suite')


class AvisosPermisosTests(APITestCase):

    def setUp(self):
        self.url = reverse('cronometro-avisos')

    def _cliente_con_rol(self, rol):
        usuario = User.objects.create_user(username='usuario.%s' % rol.lower(), password='X7k#pL2mQ9')
        PerfilUsuario.objects.create(user=usuario, rol=rol)
        cliente = APIClient()
        cliente.force_authenticate(user=usuario)
        return cliente

    def test_los_roles_autorizados_reciben_200(self):
        for rol in ROLES_AUTORIZADOS:
            with self.subTest(rol=rol):
                respuesta = self._cliente_con_rol(rol).get(self.url)
                self.assertEqual(respuesta.status_code, status.HTTP_200_OK)

    def test_los_roles_sin_relacion_con_planta_reciben_403(self):
        for rol in ROLES_DENEGADOS:
            with self.subTest(rol=rol):
                respuesta = self._cliente_con_rol(rol).get(self.url)
                self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)

    def test_un_usuario_sin_perfil_no_entra(self):
        # verificar_rol atrapa PerfilUsuario.DoesNotExist y devuelve False. Es la única
        # rama de esa función que puede volverse permisiva por descuido.
        usuario = User.objects.create_user(username='sin.perfil', password='X7k#pL2mQ9')
        cliente = APIClient()
        cliente.force_authenticate(user=usuario)

        self.assertEqual(cliente.get(self.url).status_code, status.HTTP_403_FORBIDDEN)

    def test_sin_autenticar_no_llega_a_la_guarda_de_rol(self):
        self.assertEqual(APIClient().get(self.url).status_code, status.HTTP_401_UNAUTHORIZED)


class AvisosContratoTests(APITestCase):

    def setUp(self):
        usuario = User.objects.create_user(username='lider.planta', password='X7k#pL2mQ9')
        PerfilUsuario.objects.create(user=usuario, rol='LIDER_PLANTA')
        self.client = APIClient()
        self.client.force_authenticate(user=usuario)
        self.url = reverse('cronometro-avisos')

    def test_responde_200_con_las_dos_listas(self):
        # 200 y no 204: la franja está siempre presente, incluso vacía.
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertEqual(respuesta.data, {'sin_finalizar': [], 'cerrados_recientes': []})

    def test_no_acepta_metodos_de_escritura(self):
        # Este GET dispara el barrido, que escribe. Fijar que ningún otro método entra
        # mantiene esa anomalía confinada a un único verbo.
        for peticion in (self.client.post, self.client.put, self.client.patch, self.client.delete):
            with self.subTest(metodo=peticion.__name__):
                self.assertEqual(peticion(self.url).status_code,
                                 status.HTTP_405_METHOD_NOT_ALLOWED)


class BaseAvisos(APITestCase):
    """Un DOM y un turno-día de 540 minutos sobre los que colgar cronómetros.

    Sin pruebas propias, para que las dos clases que heredan no ejecuten las de la otra.

    El escenario se ancla al reloj real: la vista llama a timezone.now() por su cuenta y
    no admite que se le inyecte el instante."""

    def setUp(self):
        usuario = User.objects.create_user(username='lider.barrido', password='X7k#pL2mQ9')
        PerfilUsuario.objects.create(user=usuario, rol='LIDER_PLANTA')
        self.client = APIClient()
        self.client.force_authenticate(user=usuario)
        self.url = reverse('cronometro-avisos')

        self.hoy = timezone.localdate()
        # turno_id explícito: HORAS_SALIDA se indexa por (turno, jornada), así que con
        # otro id la hora de salida sería nula y las marcas dejarían de probar nada.
        self.turno = Turno.objects.create(turno_id=1, nombre_turno='Turno de prueba')
        self.turno_dia = RegistroTurnoDia.objects.create(
            turno=self.turno, fecha=self.hoy, numero_operarios=6, minutos_totales=540,
        )
        cliente = Cliente.objects.create(nombre_cliente='Cliente de prueba')
        self.dom = Dom.objects.create(
            nombre_cliente=cliente,
            tipo_estado_dom='PRODUCCION',
            fecha_solicitada_cliente=self.hoy + timedelta(days=30),
            responsable='Responsable de prueba',
        )

    def _cronometro(self, numero, hace_minutos):
        planeacion = RegistroPlaneacion.objects.create(
            dom=self.dom, numero_registro=numero,
            turno=self.turno, fecha_planeacion=self.hoy,
        )
        produccion = RegistroProduccion.objects.create(
            registro_planeacion=planeacion, numero_registro=numero,
        )
        return RegistroTiempoProduccion.objects.create(
            registro_produccion=produccion, estado='EN_CURSO',
            inicio=timezone.now() - timedelta(minutes=hace_minutos),
        )

    def _ids(self, respuesta, clave):
        return [renglon['id'] for renglon in respuesta.data[clave]]


class AvisosBarridoTests(BaseAvisos):
    """El GET barre antes de listar, así que lo cerrado en esta misma petición ya sale
    en su sección — y lo que sigue abierto sigue estando."""

    def test_el_pasado_de_tope_cambia_de_seccion_en_la_misma_respuesta(self):
        """700 minutos superan el tope de 600 — jornada de 540 más 60 de margen."""
        olvidado = self._cronometro(numero=1, hace_minutos=700)

        respuesta = self.client.get(self.url)

        self.assertNotIn(olvidado.id, self._ids(respuesta, 'sin_finalizar'))
        self.assertIn(olvidado.id, self._ids(respuesta, 'cerrados_recientes'))

    def test_el_pasado_de_tope_queda_cerrado_en_la_base(self):
        olvidado = self._cronometro(numero=1, hace_minutos=700)

        self.client.get(self.url)

        olvidado.refresh_from_db()
        self.assertEqual(olvidado.estado, 'FINALIZADO')
        self.assertEqual(olvidado.motivo_cierre, RegistroTiempoProduccion.MOTIVO_TECHO)
        self.assertEqual(olvidado.minutos_totales, 600)

    def test_el_que_va_dentro_del_tope_sigue_abierto_y_listado(self):
        vivo = self._cronometro(numero=1, hace_minutos=120)

        respuesta = self.client.get(self.url)

        self.assertIn(vivo.id, self._ids(respuesta, 'sin_finalizar'))
        self.assertEqual(self._ids(respuesta, 'cerrados_recientes'), [])
        vivo.refresh_from_db()
        self.assertEqual(vivo.estado, 'EN_CURSO')

    def test_el_barrido_separa_a_los_dos_en_una_sola_peticion(self):
        olvidado = self._cronometro(numero=1, hace_minutos=700)
        vivo = self._cronometro(numero=2, hace_minutos=120)

        respuesta = self.client.get(self.url)

        self.assertEqual(self._ids(respuesta, 'sin_finalizar'), [vivo.id])
        self.assertEqual(self._ids(respuesta, 'cerrados_recientes'), [olvidado.id])

    def test_un_get_sin_nada_que_cerrar_no_deja_rastro(self):
        # La contrapartida de que un GET escriba: cuando no hay nada que cerrar, no
        # escribe. Esta prueba no podía fallar antes del barrido; ahora sí.
        self._cronometro(numero=1, hace_minutos=120)

        self.client.get(self.url)

        self.assertEqual(AuditoriaDom.objects.count(), 0)

    def test_el_cierre_deja_su_fila_de_auditoria_sin_autor(self):
        self._cronometro(numero=1, hace_minutos=700)

        self.client.get(self.url)

        fila = AuditoriaDom.objects.get()
        self.assertEqual(fila.accion, 'CIERRE_AUTOMATICO')
        self.assertIsNone(fila.usuario)
        self.assertIsNone(fila.ip)

    def test_un_cronometro_sin_jornada_determinable_no_desaparece(self):
        """Sin turno-día rige el tope de reserva de 600: a los 120 minutos sigue vivo."""
        planeacion = RegistroPlaneacion.objects.create(
            dom=self.dom, numero_registro=9, turno=None, fecha_planeacion=None,
        )
        produccion = RegistroProduccion.objects.create(
            registro_planeacion=planeacion, numero_registro=9,
        )
        huerfano = RegistroTiempoProduccion.objects.create(
            registro_produccion=produccion, estado='EN_CURSO',
            inicio=timezone.now() - timedelta(minutes=120),
        )

        respuesta = self.client.get(self.url)

        self.assertIn(huerfano.id, self._ids(respuesta, 'sin_finalizar'))


class AvisosInclusionTests(BaseAvisos):
    """Qué entra en cada lista, que es lo que más fácilmente se erosiona: un .filter()
    de más parece una optimización y no rompe ninguna otra prueba."""

    def _cerrado_por_el_sistema(self, numero, hace_horas, fin=None):
        cronometro = self._cronometro(numero=numero, hace_minutos=60)
        cronometro.estado = 'FINALIZADO'
        cronometro.fin = fin or timezone.now()
        cronometro.cerrado_por_sistema = timezone.now() - timedelta(hours=hace_horas)
        cronometro.motivo_cierre = RegistroTiempoProduccion.MOTIVO_TECHO
        cronometro.save()
        return cronometro

    def test_un_pausado_se_lista_igual_que_uno_en_curso(self):
        pausado = self._cronometro(numero=1, hace_minutos=120)
        pausado.estado = 'PAUSADO'
        pausado.save()
        PausaTiempoProduccion.objects.create(
            registro_tiempo=pausado, inicio_pausa=timezone.now() - timedelta(minutes=30),
        )

        respuesta = self.client.get(self.url)

        self.assertIn(pausado.id, self._ids(respuesta, 'sin_finalizar'))

    def test_se_lista_el_de_otro_turno(self):
        otro_turno = Turno.objects.create(turno_id=3, nombre_turno='Turno de tarde')
        RegistroTurnoDia.objects.create(
            turno=otro_turno, fecha=self.hoy, numero_operarios=4, minutos_totales=420,
        )
        ajeno = self._cronometro(numero=1, hace_minutos=60)
        planeacion = ajeno.registro_produccion.registro_planeacion
        planeacion.turno = otro_turno
        planeacion.save()

        respuesta = self.client.get(self.url)

        self.assertIn(ajeno.id, self._ids(respuesta, 'sin_finalizar'))

    def test_se_lista_el_de_una_planeacion_de_ayer(self):
        """El olvidado de verdad es de otro día: filtrar por hoy lo escondería."""
        rezagado = self._cronometro(numero=1, hace_minutos=60)
        planeacion = rezagado.registro_produccion.registro_planeacion
        planeacion.fecha_planeacion = self.hoy - timedelta(days=1)
        planeacion.save()

        respuesta = self.client.get(self.url)

        self.assertIn(rezagado.id, self._ids(respuesta, 'sin_finalizar'))

    def test_el_cerrado_hace_47_horas_sigue_en_la_ventana(self):
        reciente = self._cerrado_por_el_sistema(numero=1, hace_horas=47)

        respuesta = self.client.get(self.url)

        self.assertIn(reciente.id, self._ids(respuesta, 'cerrados_recientes'))

    def test_el_cerrado_hace_49_horas_ya_no(self):
        antiguo = self._cerrado_por_el_sistema(numero=1, hace_horas=49)

        respuesta = self.client.get(self.url)

        self.assertNotIn(antiguo.id, self._ids(respuesta, 'cerrados_recientes'))

    def test_la_ventana_se_mide_desde_la_intervencion_y_no_desde_el_fin(self):
        """El cronómetro 40 real: fin del 2 de agosto, cerrado el 25. Medido sobre fin
        no se habría visto nunca."""
        rezagado = self._cerrado_por_el_sistema(
            numero=1, hace_horas=1, fin=timezone.now() - timedelta(days=23),
        )

        respuesta = self.client.get(self.url)

        self.assertIn(rezagado.id, self._ids(respuesta, 'cerrados_recientes'))

    def test_el_finalizado_por_una_persona_no_sale_en_ninguna_lista(self):
        humano = self._cronometro(numero=1, hace_minutos=60)
        humano.estado = 'FINALIZADO'
        humano.fin = timezone.now()
        humano.save()

        respuesta = self.client.get(self.url)

        self.assertNotIn(humano.id, self._ids(respuesta, 'sin_finalizar'))
        self.assertNotIn(humano.id, self._ids(respuesta, 'cerrados_recientes'))


class AvisosConsultasTests(BaseAvisos):
    """El coste del listado no depende de cuántos cronómetros haya.

    Constante y no fórmula sobre N: una fórmula pasaría igual si el bucle empezara a
    consultar, que es justo lo que estas pruebas existen para impedir.

    El perfil del usuario no entra en la cuenta porque force_authenticate reutiliza la
    instancia de setUp, que ya trae la relación cacheada. En producción hay una consulta
    más, y autenticar aquí con token cambiaría el número sin que existiera ningún N+1.

    Ninguno de estos escenarios cierra un cronómetro, a propósito: el barrido sí gasta
    consultas por cada uno que cierra, y eso es correcto e inevitable. Lo que se fija aquí
    es el coste del listado.
    """

    def test_uno_solo_cuesta_cuatro(self):
        self._cronometro(numero=1, hace_minutos=120)

        with self.assertNumQueries(CONSULTAS_DEL_ENDPOINT):
            self.client.get(self.url)

    def test_seis_cuestan_lo_mismo(self):
        for numero in range(1, 7):
            self._cronometro(numero=numero, hace_minutos=120)

        with self.assertNumQueries(CONSULTAS_DEL_ENDPOINT):
            self.client.get(self.url)

    def test_las_pausas_tampoco_lo_hacen_crecer(self):
        # Aquí volvería a aparecer el N+1 si alguien quitara el Prefetch o consultara
        # cronometro.pausas dentro del bucle.
        for numero in (1, 2, 3):
            cronometro = self._cronometro(numero=numero, hace_minutos=120)
            cronometro.estado = 'PAUSADO'
            cronometro.save()
            PausaTiempoProduccion.objects.create(
                registro_tiempo=cronometro,
                inicio_pausa=timezone.now() - timedelta(minutes=20),
            )

        with self.assertNumQueries(CONSULTAS_DEL_ENDPOINT):
            self.client.get(self.url)

    def test_varios_turnos_dia_se_resuelven_en_una_sola_consulta(self):
        """Tres pares (turno, fecha) distintos siguen costando lo mismo: es lo que hace
        _turnos_dia_de trayendo el bloque entero en vez de fila por fila."""
        for numero, dias in ((1, 0), (2, 1), (3, 2)):
            fecha = self.hoy - timedelta(days=dias)
            RegistroTurnoDia.objects.get_or_create(
                turno=self.turno, fecha=fecha,
                defaults={'numero_operarios': 6, 'minutos_totales': 540},
            )
            cronometro = self._cronometro(numero=numero, hace_minutos=120)
            planeacion = cronometro.registro_produccion.registro_planeacion
            planeacion.fecha_planeacion = fecha
            planeacion.save()

        with self.assertNumQueries(CONSULTAS_DEL_ENDPOINT):
            self.client.get(self.url)

    def test_el_turno_de_las_pruebas_resuelve_hora_de_salida(self):
        """Salvaguarda del escenario, no del endpoint: si el turno dejara de tener un id
        que HORAS_SALIDA conoce, las marcas de la franja dejarían de probar nada sin que
        fallara ninguna prueba."""
        self.assertIsNotNone(hora_salida(self.turno_dia))


class RenglonTests(SimpleTestCase):
    """Los constructores del renglón, llamados directamente con el instante que haga falta.

    Es la única forma de cubrir por_terminar: compara contra una hora de salida fija, así
    que a través del endpoint la prueba sólo pasaría si corriera dentro de esos 45 minutos.
    La alternativa —que la vista aceptara un `ahora` inyectable— sería una afordanza de
    producción que existiría únicamente para las pruebas.

    Sin base de datos: los objetos se arman en memoria y nada se guarda.
    """

    SALIDA = timezone.make_aware(datetime(2026, 8, 25, 16, 0))

    def _cronometro(self, estado='EN_CURSO'):
        planeacion = RegistroPlaneacion(
            dom_id=59, numero_registro=2, fecha_planeacion=date(2026, 8, 25),
        )
        produccion = RegistroProduccion(registro_planeacion=planeacion, numero_registro=1)
        return RegistroTiempoProduccion(
            id=40, registro_produccion=produccion, estado=estado,
            inicio=self.SALIDA - timedelta(hours=8),
        )

    def _base(self, ahora):
        return views._renglon_base(self._cronometro(), self.SALIDA, ahora)

    def test_la_identidad_completa_viaja_en_el_renglon(self):
        renglon = self._base(self.SALIDA)

        self.assertEqual(renglon['id'], 40)
        self.assertEqual(renglon['dom_id'], 59)
        self.assertEqual(renglon['planeacion'], 2)
        self.assertEqual(renglon['produccion'], 1)
        self.assertEqual(renglon['estado'], 'EN_CURSO')

    def test_la_hora_de_salida_viaja_formateada(self):
        self.assertEqual(self._base(self.SALIDA)['hora_salida'], '16:00')

    def test_sin_usuario_el_iniciador_es_nulo(self):
        self.assertIsNone(self._base(self.SALIDA)['inicio_por'])

    def test_a_treinta_minutos_de_la_salida_esta_por_terminar(self):
        renglon = self._base(self.SALIDA - timedelta(minutes=30))

        self.assertTrue(renglon['por_terminar'])
        self.assertFalse(renglon['turno_terminado'])

    def test_a_dos_horas_de_la_salida_no_hay_ninguna_marca(self):
        renglon = self._base(self.SALIDA - timedelta(hours=2))

        self.assertFalse(renglon['por_terminar'])
        self.assertFalse(renglon['turno_terminado'])

    def test_pasada_la_salida_el_turno_esta_terminado(self):
        renglon = self._base(self.SALIDA + timedelta(minutes=1))

        self.assertTrue(renglon['turno_terminado'])
        self.assertFalse(renglon['por_terminar'])

    def test_sin_jornada_determinable_no_hay_hora_ni_marcas(self):
        renglon = views._renglon_base(self._cronometro(), None, self.SALIDA)

        self.assertIsNone(renglon['hora_salida'])
        self.assertFalse(renglon['turno_terminado'])
        self.assertFalse(renglon['por_terminar'])

    def test_el_en_curso_no_lleva_claves_de_pausa(self):
        """Un campo que siempre viene vacío no informa: con el tiempo alguien lo lee como
        «no tiene pausa larga» en vez de «esta pregunta no aplica»."""
        renglon = views._renglon_en_curso(self._cronometro(), None, self.SALIDA)

        self.assertNotIn('en_pausa_desde', renglon)
        self.assertNotIn('pausa_larga', renglon)

    def test_el_pausado_lleva_su_pausa_y_su_marca(self):
        cronometro = self._cronometro(estado='PAUSADO')
        pausa = PausaTiempoProduccion(
            registro_tiempo=cronometro, inicio_pausa=self.SALIDA - timedelta(minutes=100),
        )

        renglon = views._renglon_pausado(cronometro, None, pausa, self.SALIDA)

        self.assertEqual(renglon['en_pausa_desde'], '14:20')
        self.assertTrue(renglon['pausa_larga'])

    def test_una_pausa_corta_no_se_marca(self):
        cronometro = self._cronometro(estado='PAUSADO')
        pausa = PausaTiempoProduccion(
            registro_tiempo=cronometro, inicio_pausa=self.SALIDA - timedelta(minutes=20),
        )

        renglon = views._renglon_pausado(cronometro, None, pausa, self.SALIDA)

        self.assertFalse(renglon['pausa_larga'])

    def test_un_pausado_sin_pausa_abierta_no_tumba_el_renglon(self):
        cronometro = self._cronometro(estado='PAUSADO')

        renglon = views._renglon_pausado(cronometro, None, None, self.SALIDA)

        self.assertIsNone(renglon['en_pausa_desde'])
        self.assertFalse(renglon['pausa_larga'])


class OrdenDeLaFranjaTests(SimpleTestCase):
    """Lo grave arriba, y cada sección con su propio criterio."""

    def test_en_curso_manda_el_turno_terminado(self):
        terminado = {'turno_terminado': True, 'por_terminar': False}
        por_salir = {'turno_terminado': False, 'por_terminar': True}
        tranquilo = {'turno_terminado': False, 'por_terminar': False}

        self.assertEqual(
            sorted([tranquilo, por_salir, terminado], key=views._orden_en_curso),
            [terminado, por_salir, tranquilo],
        )

    def test_en_pausados_la_pausa_larga_va_antes_que_el_turno_terminado(self):
        """La pausa larga es un aviso con plazo —30 minutos hasta el cierre automático— y
        el turno terminado es un hecho consumado."""
        pausa = {'pausa_larga': True, 'turno_terminado': False}
        terminado = {'pausa_larga': False, 'turno_terminado': True}
        tranquilo = {'pausa_larga': False, 'turno_terminado': False}

        self.assertEqual(
            sorted([tranquilo, terminado, pausa], key=views._orden_pausados),
            [pausa, terminado, tranquilo],
        )


class RenglonPorEndpointTests(BaseAvisos):
    """Que el cableado esté hecho: las claves llegan y las secciones se concatenan."""

    def test_el_renglon_llega_con_todas_sus_claves(self):
        cronometro = self._cronometro(numero=1, hace_minutos=120)

        renglon = self.client.get(self.url).data['sin_finalizar'][0]

        self.assertEqual(renglon['id'], cronometro.id)
        self.assertEqual(renglon['dom_id'], self.dom.dom_id)
        self.assertEqual(renglon['planeacion'], 1)
        self.assertEqual(renglon['produccion'], 1)
        self.assertEqual(renglon['hora_salida'], '16:00')

    def test_la_fecha_de_hoy_viaja_y_se_marca_como_tal(self):
        self._cronometro(numero=1, hace_minutos=120)

        renglon = self.client.get(self.url).data['sin_finalizar'][0]

        self.assertEqual(renglon['fecha_planeacion'], self.hoy.strftime('%d/%m/%Y'))
        self.assertTrue(renglon['es_hoy'])

    def test_la_de_ayer_no_se_marca_como_hoy(self):
        """Sin es_hoy, un renglón sin fecha visible sería ambiguo entre ser de hoy, no
        tener fecha, o estar mal pintado."""
        cronometro = self._cronometro(numero=1, hace_minutos=120)
        planeacion = cronometro.registro_produccion.registro_planeacion
        planeacion.fecha_planeacion = self.hoy - timedelta(days=1)
        planeacion.save()

        renglon = self.client.get(self.url).data['sin_finalizar'][0]

        self.assertFalse(renglon['es_hoy'])

    def test_sin_fecha_ni_es_hoy_ni_hora_de_salida(self):
        planeacion = RegistroPlaneacion.objects.create(
            dom=self.dom, numero_registro=9, turno=None, fecha_planeacion=None,
        )
        produccion = RegistroProduccion.objects.create(
            registro_planeacion=planeacion, numero_registro=9,
        )
        RegistroTiempoProduccion.objects.create(
            registro_produccion=produccion, estado='EN_CURSO',
            inicio=timezone.now() - timedelta(minutes=60),
        )

        renglon = self.client.get(self.url).data['sin_finalizar'][0]

        self.assertIsNone(renglon['fecha_planeacion'])
        self.assertFalse(renglon['es_hoy'])
        self.assertIsNone(renglon['hora_salida'])

    def test_los_en_curso_van_antes_que_los_pausados(self):
        en_curso = self._cronometro(numero=1, hace_minutos=120)
        pausado = self._cronometro(numero=2, hace_minutos=120)
        pausado.estado = 'PAUSADO'
        pausado.save()
        PausaTiempoProduccion.objects.create(
            registro_tiempo=pausado, inicio_pausa=timezone.now() - timedelta(minutes=10),
        )

        ids = self._ids(self.client.get(self.url), 'sin_finalizar')

        self.assertEqual(ids, [en_curso.id, pausado.id])

    def test_el_renglon_de_cerrados_dice_que_paso_y_cuanto_quedo(self):
        olvidado = self._cronometro(numero=1, hace_minutos=700)

        renglon = self.client.get(self.url).data['cerrados_recientes'][0]

        self.assertEqual(renglon['id'], olvidado.id)
        self.assertEqual(renglon['motivo_cierre'], RegistroTiempoProduccion.MOTIVO_TECHO)
        self.assertEqual(renglon['minutos_totales'], 600)
        self.assertIsNotNone(renglon['fin'])
        self.assertIsNotNone(renglon['cerrado_por_sistema'])

    def test_los_cerrados_no_llevan_marcas_ni_estado(self):
        self._cronometro(numero=1, hace_minutos=700)

        renglon = self.client.get(self.url).data['cerrados_recientes'][0]

        for clave in ('estado', 'hora_salida', 'turno_terminado', 'por_terminar'):
            with self.subTest(clave=clave):
                self.assertNotIn(clave, renglon)
