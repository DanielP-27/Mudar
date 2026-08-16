"""Las reglas de cantidad de la cadena: qué producto puede planearse, cuánto puede
planearse y cuánto puede producirse.

La cadena de un producto tiene tres eslabones — elaborada <= proyectada <= pedida — y
cada clase de esta suite vigila uno de sus extremos.

Las dos reglas viven en las vistas y **son sobre el acumulado**, que es lo que las hace
imposibles de comprobar desde el frontend: «proyectada ≤ pedida» suma lo ya proyectado en
las OTRAS planeaciones del mismo DOM, y «elaborada ≤ proyectada» suma lo elaborado en los
OTROS registros de producción de la misma planeación. Una pantalla solo ve el registro
que tiene delante.

Estas pruebas **no fallan primero**: las reglas ya existen y funcionan. Su trabajo es otro
—fijar el comportamiento actual antes de que el PUT atómico las mueva—. Hoy validan un
producto por llamada; el diseño nuevo validará el conjunto entrante de una sola vez, y
esta suite es lo único que dirá si la regla sobrevivió al traslado.

Cada rechazo se comprueba **por su mensaje** y no solo por el 401/400. Las dos vistas
pueden devolver 400 por capacidad del turno o por turno-día ausente, así que un test que
solo mirara el código de estado pasaría en verde sin haber ejercitado la regla.
"""
from datetime import date

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from server.models import (
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

URL_PLANEACION = '/api/productos-planeacion/'
URL_PRODUCCION = '/api/productos-produccion/'

FECHA = date(2026, 9, 1)


class BaseTopes(APITestCase):
    """Un DOM con un producto de 20 unidades y un turno con capacidad de sobra, para que
    lo único que pueda rechazar sea el tope bajo prueba."""

    def setUp(self):
        self.admin = User.objects.create_user(username='admin.topes', password='X7k#pL2mQ9')
        PerfilUsuario.objects.create(user=self.admin, rol='ADMIN')
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

        self.producto = Productos.objects.create(
            nombre_producto='Tanque A', tiempo_produccion_unitario=30,
        )
        self.turno = Turno.objects.create(nombre_turno='Turno de prueba')
        # 6 operarios x 420 min = 2520 minutos-persona. El producto entero son 600.
        RegistroTurnoDia.objects.create(
            turno=self.turno, fecha=FECHA, numero_operarios=6, minutos_totales=420,
        )
        self.cliente = Cliente.objects.create(nombre_cliente='Cliente de prueba')
        self.dom = Dom.objects.create(
            nombre_cliente=self.cliente,
            tipo_estado_dom='PRODUCCION',
            fecha_solicitada_cliente=date(2026, 9, 30),
            responsable='Responsable de prueba',
        )
        self.producto_dom = ProductosDom.objects.create(
            productoDom=self.dom, tipo_producto=self.producto, cantidad_pedido=20,
        )
        # Dos planeaciones del mismo DOM, mismo turno y fecha: es el escenario en que el
        # acumulado importa, y no es raro — hoy 21 de 62 DOMs tienen más de una.
        self.planeacion = RegistroPlaneacion.objects.create(
            dom=self.dom, numero_registro=1, turno=self.turno, fecha_planeacion=FECHA,
        )
        self.otra_planeacion = RegistroPlaneacion.objects.create(
            dom=self.dom, numero_registro=2, turno=self.turno, fecha_planeacion=FECHA,
        )

    def proyectar(self, planeacion, cantidad):
        return self.client.post(URL_PLANEACION, {
            'registro_planeacion': planeacion.id,
            'dom_producto': self.producto_dom.id,
            'cantidad_proyectada': cantidad,
        }, format='json')


class ProyectadaNoSuperaLaPedidaTests(BaseTopes):

    def test_proyectar_mas_de_lo_pedido_se_rechaza(self):
        respuesta = self.proyectar(self.planeacion, 21)

        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST, respuesta.data)
        self.assertIn('supera la cantidad pedida', respuesta.data['error'])
        self.assertEqual(ProductoPlaneacion.objects.count(), 0)

    def test_proyectar_exactamente_lo_pedido_se_acepta(self):
        """Control del borde por el lado bueno: 20 de 20 es válido."""
        respuesta = self.proyectar(self.planeacion, 20)

        self.assertEqual(respuesta.status_code, status.HTTP_201_CREATED, respuesta.data)
        self.assertEqual(ProductoPlaneacion.objects.get().cantidad_proyectada, 20)

    def test_el_tope_es_el_acumulado_entre_planeaciones(self):
        """15 en una planeación y 10 en otra suman 25 sobre 20 pedidas. Cada una por
        separado es válida; es la suma la que no. Ninguna pantalla puede ver esto."""
        self.proyectar(self.planeacion, 15)

        respuesta = self.proyectar(self.otra_planeacion, 10)

        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST, respuesta.data)
        self.assertIn('supera la cantidad pedida', respuesta.data['error'])
        self.assertEqual(respuesta.data['cantidad_ya_proyectada'], 15)
        self.assertEqual(respuesta.data['disponible'], 5)
        self.assertEqual(ProductoPlaneacion.objects.count(), 1)

    def test_el_acumulado_deja_pasar_lo_que_falta(self):
        """Simétrico del anterior: 15 más 5 son exactamente las 20 pedidas."""
        self.proyectar(self.planeacion, 15)

        respuesta = self.proyectar(self.otra_planeacion, 5)

        self.assertEqual(respuesta.status_code, status.HTTP_201_CREATED, respuesta.data)
        self.assertEqual(ProductoPlaneacion.objects.count(), 2)

    def test_al_editar_no_se_cuenta_la_propia_fila(self):
        """Subir de 15 a 20 la misma línea debe pasar. Si el acumulado no excluyera la
        fila que se está editando, sumaría 15 + 20 y rechazaría un cambio legítimo."""
        self.proyectar(self.planeacion, 15)
        pp = ProductoPlaneacion.objects.get()

        respuesta = self.client.put(
            f'{URL_PLANEACION}{pp.id}/', {'cantidad_proyectada': 20}, format='json',
        )

        self.assertEqual(respuesta.status_code, status.HTTP_200_OK, respuesta.data)
        pp.refresh_from_db()
        self.assertEqual(pp.cantidad_proyectada, 20)


class PertenenciaDelProductoTests(BaseTopes):
    """Una planeación solo puede planear productos de SU DOM.

    No es alcanzable desde la pantalla —el formulario solo pinta los productos del
    propio DOM— pero sí por la API. Y el daño es invisible: la línea ajena no se
    dibuja en ningún sitio y aun así entra en los totales del DOM y hace que el tope
    de cantidad se compare contra el pedido equivocado."""

    def test_no_se_puede_planear_un_producto_de_otro_dom(self):
        otro_dom = Dom.objects.create(
            nombre_cliente=self.cliente,
            tipo_estado_dom='PRODUCCION',
            fecha_solicitada_cliente=date(2026, 9, 30),
            responsable='Responsable de prueba',
        )
        producto_ajeno = ProductosDom.objects.create(
            productoDom=otro_dom, tipo_producto=self.producto, cantidad_pedido=20,
        )

        respuesta = self.client.post(URL_PLANEACION, {
            'registro_planeacion': self.planeacion.id,
            'dom_producto': producto_ajeno.id,
            'cantidad_proyectada': 5,
        }, format='json')

        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST, respuesta.data)
        self.assertIn('no pertenece a este DOM', respuesta.data['error'])
        self.assertEqual(ProductoPlaneacion.objects.count(), 0)


class ProyectadaNoBajaDeLoElaboradoTests(BaseTopes):
    """El eslabón elaborada <= proyectada, atacado desde el lado en que la proyectada
    baja. El endpoint de producción ya lo vigila cuando la elaborada sube; nadie lo
    vigilaba al editar la planeación hacia atrás."""

    def setUp(self):
        super().setUp()
        self.proyectar(self.planeacion, 20)
        self.pp = ProductoPlaneacion.objects.get()
        self.jornada = RegistroProduccion.objects.create(
            registro_planeacion=self.planeacion, numero_registro=1,
            numero_personas_asignadas=3,
        )
        ProductoProduccion.objects.create(
            registro_produccion=self.jornada,
            producto_planeacion=self.pp,
            cantidad_elaborada=13,
        )

    def test_no_se_puede_proyectar_menos_de_lo_ya_elaborado(self):
        """Bajar a 10 con 13 fabricadas dejaría cantidad_pendiente en -3 y
        cantidad_disponible_produccion bloqueado de forma permanente."""
        respuesta = self.client.put(
            f'{URL_PLANEACION}{self.pp.id}/', {'cantidad_proyectada': 10}, format='json',
        )

        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST, respuesta.data)
        self.assertIn('menos de lo ya elaborado', respuesta.data['error'])
        self.pp.refresh_from_db()
        self.assertEqual(self.pp.cantidad_proyectada, 20)

    def test_bajar_hasta_exactamente_lo_elaborado_se_acepta(self):
        """«Planeé 20, salieron 13, ajusto el plan a lo que salió» es una corrección
        legítima. La comparación es estricta por esto."""
        respuesta = self.client.put(
            f'{URL_PLANEACION}{self.pp.id}/', {'cantidad_proyectada': 13}, format='json',
        )

        self.assertEqual(respuesta.status_code, status.HTTP_200_OK, respuesta.data)
        self.pp.refresh_from_db()
        self.assertEqual(self.pp.cantidad_proyectada, 13)


class ElaboradaNoSuperaLaProyectadaTests(BaseTopes):

    def setUp(self):
        super().setUp()
        self.pp = ProductoPlaneacion.objects.create(
            registro_planeacion=self.planeacion,
            dom_producto=self.producto_dom,
            cantidad_proyectada=20,
        )
        # Dos jornadas sobre la misma planeación: el molde de la producción parcial.
        self.jornada_uno = RegistroProduccion.objects.create(
            registro_planeacion=self.planeacion, numero_registro=1,
            numero_personas_asignadas=3,
        )
        self.jornada_dos = RegistroProduccion.objects.create(
            registro_planeacion=self.planeacion, numero_registro=2,
            numero_personas_asignadas=3,
        )

    def elaborar(self, jornada, cantidad):
        return self.client.post(URL_PRODUCCION, {
            'registro_produccion': jornada.id,
            'producto_planeacion': self.pp.id,
            'cantidad_elaborada': cantidad,
        }, format='json')

    def test_elaborar_mas_de_lo_proyectado_se_rechaza(self):
        respuesta = self.elaborar(self.jornada_uno, 21)

        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST, respuesta.data)
        self.assertIn('supera la cantidad proyectada', respuesta.data['error'])
        self.assertEqual(ProductoProduccion.objects.count(), 0)

    def test_el_tope_es_el_acumulado_entre_jornadas(self):
        """13 el primer día y 10 el segundo suman 23 sobre 20 proyectadas."""
        self.elaborar(self.jornada_uno, 13)

        respuesta = self.elaborar(self.jornada_dos, 10)

        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST, respuesta.data)
        self.assertIn('supera la cantidad proyectada', respuesta.data['error'])
        self.assertEqual(ProductoProduccion.objects.count(), 1)

    def test_el_acumulado_entre_jornadas_deja_completar(self):
        """Simétrico y esencial: 13 más 7 completan las 20. Si esto se rompiera, una
        producción incompleta no podría terminarse nunca."""
        self.elaborar(self.jornada_uno, 13)

        respuesta = self.elaborar(self.jornada_dos, 7)

        self.assertEqual(respuesta.status_code, status.HTTP_201_CREATED, respuesta.data)
        self.assertEqual(self.pp.cantidad_elaborada, 20)
