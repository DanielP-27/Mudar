"""La planeación y sus cantidades se guardan en una sola petición y en una sola
transacción: o se escribe todo, o no se escribe nada.

Antes eran N llamadas —una para el registro y una por producto— sin nada que las uniera.
El candado viajaba en la primera, así que un clic que cerrara la etapa y trajera
cantidades dejaba la planeación cerrada y vacía, sin salida para un PLANEADOR porque el
desbloqueo es solo de ADMIN. Y un rechazo a mitad del recorrido dejaba escrito lo
anterior.

Estas pruebas cubren lo que solo existe con el endpoint nuevo. Las reglas de cantidad en
sí están fijadas aparte, en test_topes_de_cantidad.
"""
from datetime import date

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from server.models import (
    AuditoriaDom,
    Cliente,
    Dom,
    PerfilUsuario,
    ProductoPlaneacion,
    ProductoProduccion,
    Productos,
    ProductosDom,
    RegistroPlaneacion,
    RegistroProduccion,
    RegistroTurnoDia,
    Turno,
)

FECHA = date(2026, 9, 1)


class BaseAtomico(APITestCase):

    def setUp(self):
        self.admin = User.objects.create_user(username='admin.atomico', password='X7k#pL2mQ9')
        PerfilUsuario.objects.create(user=self.admin, rol='ADMIN')
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

        self.producto = Productos.objects.create(
            nombre_producto='Tanque A', tiempo_produccion_unitario=30,
        )
        self.otro_producto = Productos.objects.create(
            nombre_producto='Tanque B', tiempo_produccion_unitario=30,
        )
        self.turno = Turno.objects.create(nombre_turno='Turno de prueba')
        self.cliente = Cliente.objects.create(nombre_cliente='Cliente de prueba')
        self.dom = Dom.objects.create(
            nombre_cliente=self.cliente,
            tipo_estado_dom='PRODUCCION',
            fecha_solicitada_cliente=date(2026, 9, 30),
            responsable='Responsable de prueba',
        )
        self.producto_a = ProductosDom.objects.create(
            productoDom=self.dom, tipo_producto=self.producto, cantidad_pedido=20,
        )
        self.producto_b = ProductosDom.objects.create(
            productoDom=self.dom, tipo_producto=self.otro_producto, cantidad_pedido=20,
        )
        # Sin turno ni fecha: los trae el PUT, que es el caso real de la pantalla.
        self.planeacion = RegistroPlaneacion.objects.create(
            dom=self.dom, numero_registro=1,
        )
        self.url = f'/api/planeacion/{self.planeacion.id}/'

    def guardar(self, **extra):
        cuerpo = {
            'turno': self.turno.turno_id,
            'fecha_planeacion': str(FECHA),
            'numero_operarios': 6,
            'minutos_totales': 420,
        }
        cuerpo.update(extra)
        return self.client.put(self.url, cuerpo, format='json')


class UnSoloGuardadoTests(BaseAtomico):

    def test_cerrar_y_escribir_cantidades_en_un_solo_put(self):
        """El caso que hoy deja la planeación cerrada y vacía: el candado y las
        cantidades llegan juntos y las dos cosas tienen que quedar guardadas."""
        respuesta = self.guardar(
            planeacion_completa=True,
            productos_planeacion=[
                {'dom_producto': self.producto_a.id, 'cantidad_proyectada': 10},
                {'dom_producto': self.producto_b.id, 'cantidad_proyectada': 10},
            ],
        )

        self.assertEqual(respuesta.status_code, status.HTTP_200_OK, respuesta.data)
        self.planeacion.refresh_from_db()
        self.assertTrue(self.planeacion.planeacion_completa)
        self.assertEqual(ProductoPlaneacion.objects.count(), 2)
        self.assertEqual(
            sorted(ProductoPlaneacion.objects.values_list('cantidad_proyectada', flat=True)),
            [10, 10],
        )
        self.assertEqual(RegistroTurnoDia.objects.count(), 1)

    def test_una_cantidad_no_enviada_conserva_su_valor(self):
        """Casilla vacía es «no enviar», no «borrar». El olvido no destruye nada."""
        self.guardar(productos_planeacion=[
            {'dom_producto': self.producto_a.id, 'cantidad_proyectada': 10},
            {'dom_producto': self.producto_b.id, 'cantidad_proyectada': 10},
        ])

        respuesta = self.guardar(productos_planeacion=[
            {'dom_producto': self.producto_a.id, 'cantidad_proyectada': 15},
        ])

        self.assertEqual(respuesta.status_code, status.HTTP_200_OK, respuesta.data)
        a = ProductoPlaneacion.objects.get(dom_producto=self.producto_a)
        b = ProductoPlaneacion.objects.get(dom_producto=self.producto_b)
        self.assertEqual(a.cantidad_proyectada, 15)
        self.assertEqual(b.cantidad_proyectada, 10, 'La línea no enviada perdió su valor.')

    def test_la_auditoria_deja_una_sola_fila(self):
        """Una acción del usuario, una fila. Antes dejaba una por llamada."""
        self.guardar(productos_planeacion=[
            {'dom_producto': self.producto_a.id, 'cantidad_proyectada': 10},
            {'dom_producto': self.producto_b.id, 'cantidad_proyectada': 10},
        ])

        self.assertEqual(AuditoriaDom.objects.filter(dom=self.dom).count(), 1)


class TodoONadaTests(BaseAtomico):

    def test_si_una_cantidad_se_rechaza_no_se_escribe_ninguna(self):
        """El daño original: el recorrido escribía hasta el punto del fallo."""
        respuesta = self.guardar(productos_planeacion=[
            {'dom_producto': self.producto_a.id, 'cantidad_proyectada': 10},
            {'dom_producto': self.producto_b.id, 'cantidad_proyectada': 25},
        ])

        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST, respuesta.data)
        self.assertEqual(
            ProductoPlaneacion.objects.count(), 0,
            'Se escribió la primera cantidad pese a que la segunda se rechazó.'
        )

    def test_el_turno_dia_creado_desaparece_si_falla_la_capacidad(self):
        """Sin transacción, el turno-día se creaba y sobrevivía al rechazo. Con un
        operario la jornada da 420 minutos y las cantidades piden 600."""
        respuesta = self.guardar(
            numero_operarios=1,
            productos_planeacion=[
                {'dom_producto': self.producto_a.id, 'cantidad_proyectada': 20},
            ],
        )

        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST, respuesta.data)
        self.assertEqual(
            RegistroTurnoDia.objects.count(), 0,
            'El turno-día quedó creado pese a que la petición se rechazó.'
        )
        self.assertEqual(ProductoPlaneacion.objects.count(), 0)

    def test_cerrar_con_todas_las_cantidades_en_cero_se_rechaza_sin_escribir(self):
        """La guarda de la mitad B corre DESPUÉS de escribir, dentro de la transacción:
        solo así puede mirar el conjunto final en vez de pronosticarlo. Y por eso su
        rechazo tiene que deshacer lo ya escrito."""
        respuesta = self.guardar(
            planeacion_completa=True,
            productos_planeacion=[
                {'dom_producto': self.producto_a.id, 'cantidad_proyectada': 0},
                {'dom_producto': self.producto_b.id, 'cantidad_proyectada': 0},
            ],
        )

        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST, respuesta.data)
        self.planeacion.refresh_from_db()
        self.assertFalse(self.planeacion.planeacion_completa)
        self.assertEqual(
            ProductoPlaneacion.objects.count(), 0,
            'Las cantidades quedaron escritas pese a que el cierre se rechazó.'
        )
        self.assertEqual(RegistroTurnoDia.objects.count(), 0)

    def test_una_jornada_que_no_existe_en_la_ley_se_rechaza(self):
        """objects.create() no aplica los choices de minutos_totales; el serializer sí."""
        respuesta = self.guardar(minutos_totales=999)

        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST, respuesta.data)
        self.assertEqual(RegistroTurnoDia.objects.count(), 0)


class SinCantidadesTests(BaseAtomico):
    """Un PUT sin `productos_planeacion` tiene que seguir comportándose como siempre:
    el endpoint es el mismo que usan los guiones y el resto del sistema."""

    def test_un_put_sin_cantidades_guarda_la_planeacion(self):
        respuesta = self.guardar(lider_produccion='Ana')

        self.assertEqual(respuesta.status_code, status.HTTP_200_OK, respuesta.data)
        self.planeacion.refresh_from_db()
        self.assertEqual(self.planeacion.lider_produccion, 'Ana')
        self.assertEqual(ProductoPlaneacion.objects.count(), 0)


class VariosRechazosEnUnaSolaRespuestaTests(BaseAtomico):
    """El envío es un lote, así que la respuesta también tiene que serlo.

    El bucle cortaba en la primera línea inválida: con tres productos mal, el planeador
    corregía uno, guardaba, y descubría el siguiente — una vuelta de guardado por cada
    error que ya estaba ahí desde el primer intento.

    El frontend ya sabía pintar varias líneas: extraerMensajeError une lo que encuentre en
    `detalle` y ModalBase lo lista una por una. Lo que faltaba era que el backend las
    mandara, y de ahí que la lista viaje en `detalle` y no solo en `error`.
    """

    def test_dos_lineas_invalidas_vuelven_en_la_misma_respuesta(self):
        """Y por reglas distintas: una se pasa de lo pedido, la otra proyecta menos de lo
        ya elaborado. Que acumule entre reglas diferentes es lo que se fija aquí."""
        self.guardar(productos_planeacion=[
            {'dom_producto': self.producto_a.id, 'cantidad_proyectada': 10},
            {'dom_producto': self.producto_b.id, 'cantidad_proyectada': 10},
        ])
        pp_b = ProductoPlaneacion.objects.get(dom_producto=self.producto_b)
        jornada = RegistroProduccion.objects.create(
            registro_planeacion=self.planeacion, numero_registro=1,
            numero_personas_asignadas=3,
        )
        ProductoProduccion.objects.create(
            registro_produccion=jornada, producto_planeacion=pp_b,
            cantidad_elaborada=8, registrado_por=self.admin,
        )

        respuesta = self.guardar(productos_planeacion=[
            {'dom_producto': self.producto_a.id, 'cantidad_proyectada': 25},
            {'dom_producto': self.producto_b.id, 'cantidad_proyectada': 5},
        ])

        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST, respuesta.data)
        lineas = respuesta.data['detalle']['non_field_errors']
        self.assertEqual(len(lineas), 2, respuesta.data)
        self.assertIn('supera la cantidad pedida', lineas[0])
        self.assertIn('Tanque A', lineas[0])
        self.assertIn('menos de lo ya elaborado', lineas[1])
        self.assertIn('Tanque B', lineas[1])

        pp_a = ProductoPlaneacion.objects.get(dom_producto=self.producto_a)
        pp_b.refresh_from_db()
        self.assertEqual(pp_a.cantidad_proyectada, 10, 'El rechazo escribió la primera línea.')
        self.assertEqual(pp_b.cantidad_proyectada, 10, 'El rechazo escribió la segunda línea.')

    def test_una_sola_linea_invalida_tambien_usa_la_forma_nueva(self):
        """Cambio de contrato deliberado: con un solo rechazo el cuerpo ya no trae las
        cifras de esa línea —cantidad_pedida, disponible—. Ningún cliente las lee, y con
        varias líneas no habría un solo valor que reportar."""
        respuesta = self.guardar(productos_planeacion=[
            {'dom_producto': self.producto_a.id, 'cantidad_proyectada': 25},
        ])

        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST, respuesta.data)
        self.assertEqual(len(respuesta.data['detalle']['non_field_errors']), 1)
        self.assertIn('supera la cantidad pedida', respuesta.data['error'])
        self.assertNotIn('cantidad_pedida', respuesta.data)
        self.assertEqual(ProductoPlaneacion.objects.count(), 0)
