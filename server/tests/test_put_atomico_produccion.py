"""El registro de producción y sus cantidades elaboradas se guardan en una sola petición
y en una sola transacción: o se escribe todo, o no se escribe nada.

Es la misma forma que ya tiene planeación, un eslabón más abajo de la cadena, y con dos
diferencias que estas pruebas vigilan. La primera es la clave del conjunto: aquí la línea
se identifica por el producto planeado, no por el producto del DOM, y ninguna clave
foránea garantiza que ese producto planeado cuelgue de la misma planeación que el
registro. La segunda es que uno de los requisitos de cierre —el cronómetro finalizado—
no viaja en esta petición, así que el líder tiene que haberlo cerrado antes.

Las reglas de una línea en sí están fijadas aparte, en test_topes_de_cantidad.
"""
from datetime import date

from django.contrib.auth.models import User
from django.utils import timezone
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
    RegistroTiempoProduccion,
    Turno,
)

FECHA = date(2026, 9, 1)


class BaseAtomicoProduccion(APITestCase):
    """Una planeación con dos productos proyectados y una jornada de producción sin nada
    diligenciado. El cronómetro no se crea aquí: es requisito de cierre y cada prueba
    decide si su escenario lo tiene."""

    def setUp(self):
        self.admin = User.objects.create_user(username='admin.produccion', password='X7k#pL2mQ9')
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
        self.planeacion = RegistroPlaneacion.objects.create(
            dom=self.dom, numero_registro=1, turno=self.turno, fecha_planeacion=FECHA,
        )
        self.pp_a = ProductoPlaneacion.objects.create(
            registro_planeacion=self.planeacion,
            dom_producto=self.producto_a,
            cantidad_proyectada=10,
        )
        self.pp_b = ProductoPlaneacion.objects.create(
            registro_planeacion=self.planeacion,
            dom_producto=self.producto_b,
            cantidad_proyectada=10,
        )
        self.jornada = RegistroProduccion.objects.create(
            registro_planeacion=self.planeacion, numero_registro=1,
        )
        self.url = f'/api/produccion/{self.jornada.id}/'

    def cronometro_finalizado(self):
        # Las personas se confirman ANTES de iniciar el cronómetro y desde ahí el
        # serializer congela el campo. Persistirlas aquí es lo que hace que el escenario
        # sea alcanzable: un cronómetro sin personas confirmadas no existe en la pantalla.
        self.jornada.numero_personas_asignadas = 3
        self.jornada.save()
        return RegistroTiempoProduccion.objects.create(
            registro_produccion=self.jornada,
            inicio=timezone.now(), fin=timezone.now(),
            estado='FINALIZADO', minutos_totales=23,
        )

    def guardar(self, **extra):
        cuerpo = {'numero_personas_asignadas': 3}
        cuerpo.update(extra)
        return self.client.put(self.url, cuerpo, format='json')


class UnSoloGuardadoTests(BaseAtomicoProduccion):

    def test_cerrar_y_escribir_cantidades_en_un_solo_put(self):
        """El caso que justifica el cambio: el candado y las cantidades llegan juntos y
        las dos cosas tienen que quedar guardadas."""
        self.cronometro_finalizado()

        respuesta = self.guardar(
            segun_planeacion=True,
            cierre_produccion=True,
            productos_produccion=[
                {'producto_planeacion': self.pp_a.id, 'cantidad_elaborada': 8},
                {'producto_planeacion': self.pp_b.id, 'cantidad_elaborada': 6},
            ],
        )

        self.assertEqual(respuesta.status_code, status.HTTP_200_OK, respuesta.data)
        self.jornada.refresh_from_db()
        self.assertTrue(self.jornada.cierre_produccion)
        self.assertEqual(ProductoProduccion.objects.count(), 2)
        self.assertEqual(
            sorted(ProductoProduccion.objects.values_list('cantidad_elaborada', flat=True)),
            [6, 8],
        )

    def test_una_cantidad_no_enviada_conserva_su_valor(self):
        """Casilla vacía es «no enviar», no «borrar». El olvido no destruye nada."""
        self.guardar(productos_produccion=[
            {'producto_planeacion': self.pp_a.id, 'cantidad_elaborada': 8},
            {'producto_planeacion': self.pp_b.id, 'cantidad_elaborada': 6},
        ])

        respuesta = self.guardar(productos_produccion=[
            {'producto_planeacion': self.pp_a.id, 'cantidad_elaborada': 9},
        ])

        self.assertEqual(respuesta.status_code, status.HTTP_200_OK, respuesta.data)
        a = ProductoProduccion.objects.get(producto_planeacion=self.pp_a)
        b = ProductoProduccion.objects.get(producto_planeacion=self.pp_b)
        self.assertEqual(a.cantidad_elaborada, 9)
        self.assertEqual(b.cantidad_elaborada, 6, 'La línea no enviada perdió su valor.')

    def test_quien_corrige_queda_registrado_en_la_fila(self):
        """El campo guarda quién escribió la fila por última vez, no quién la creó."""
        self.guardar(productos_produccion=[
            {'producto_planeacion': self.pp_a.id, 'cantidad_elaborada': 8},
        ])
        otro = User.objects.create_user(username='lider.turno.dos', password='X7k#pL2mQ9')
        PerfilUsuario.objects.create(user=otro, rol='LIDER_PLANTA')
        self.client.force_authenticate(user=otro)

        self.guardar(productos_produccion=[
            {'producto_planeacion': self.pp_a.id, 'cantidad_elaborada': 9},
        ])

        fila = ProductoProduccion.objects.get(producto_planeacion=self.pp_a)
        self.assertEqual(fila.registrado_por, otro)

    def test_la_auditoria_separa_la_edicion_del_bloqueo(self):
        """Cerrar una etapa y editar su contenido son dos hechos, aunque viajen en el
        mismo PUT. Sin el lote eran además una fila por llamada."""
        self.cronometro_finalizado()

        self.guardar(
            segun_planeacion=True,
            cierre_produccion=True,
            productos_produccion=[
                {'producto_planeacion': self.pp_a.id, 'cantidad_elaborada': 8},
            ],
        )

        acciones = sorted(
            AuditoriaDom.objects.filter(dom=self.dom).values_list('accion', flat=True)
        )
        self.assertEqual(acciones, ['BLOQUEO_ETAPA', 'EDICION'])


class TodoONadaTests(BaseAtomicoProduccion):

    def test_si_una_cantidad_se_rechaza_no_se_escribe_ninguna(self):
        """La primera línea cabe en lo proyectado y la segunda no. Antes el recorrido
        escribía hasta el punto del fallo."""
        respuesta = self.guardar(
            segun_planeacion=True,
            productos_produccion=[
                {'producto_planeacion': self.pp_a.id, 'cantidad_elaborada': 8},
                {'producto_planeacion': self.pp_b.id, 'cantidad_elaborada': 25},
            ],
        )

        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST, respuesta.data)
        self.assertEqual(
            ProductoProduccion.objects.count(), 0,
            'Se escribió la primera cantidad pese a que la segunda se rechazó.',
        )
        self.jornada.refresh_from_db()
        self.assertIsNone(
            self.jornada.segun_planeacion,
            'El registro se guardó pese a que una de sus líneas se rechazó.',
        )

    def test_cerrar_sin_ninguna_cantidad_se_rechaza_sin_escribir(self):
        """La guarda corre DESPUÉS de escribir, dentro de la transacción: solo así puede
        mirar el conjunto final en vez de pronosticarlo. Y por eso su rechazo revierte
        también el veredicto que venía en el mismo cuerpo."""
        self.cronometro_finalizado()

        respuesta = self.guardar(
            segun_planeacion=True,
            cierre_produccion=True,
        )

        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST, respuesta.data)
        self.assertIn('cantidad', respuesta.data['error'])
        self.jornada.refresh_from_db()
        self.assertFalse(self.jornada.cierre_produccion)
        self.assertIsNone(self.jornada.segun_planeacion)

    def test_cerrar_con_todas_las_cantidades_en_cero_se_rechaza(self):
        """El umbral es mayor que cero y no «hay fila»: una jornada que no produjo nada
        no se cierra, aunque se hayan registrado ceros."""
        self.cronometro_finalizado()

        respuesta = self.guardar(
            segun_planeacion=True,
            cierre_produccion=True,
            productos_produccion=[
                {'producto_planeacion': self.pp_a.id, 'cantidad_elaborada': 0},
            ],
        )

        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST, respuesta.data)
        self.assertEqual(
            ProductoProduccion.objects.count(), 0,
            'El cero quedó escrito pese a que el cierre se rechazó.',
        )


class ElLoteRespondeComoLoteTests(BaseAtomicoProduccion):

    def test_dos_lineas_invalidas_vuelven_en_la_misma_respuesta(self):
        """Con dos productos pasados de lo proyectado, el líder debe verlos de una vez y
        no descubrir el segundo después de corregir el primero."""
        respuesta = self.guardar(productos_produccion=[
            {'producto_planeacion': self.pp_a.id, 'cantidad_elaborada': 25},
            {'producto_planeacion': self.pp_b.id, 'cantidad_elaborada': 30},
        ])

        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST, respuesta.data)
        lineas = respuesta.data['detalle']['non_field_errors']
        self.assertEqual(len(lineas), 2, respuesta.data)
        self.assertIn('Tanque A', lineas[0])
        self.assertIn('Tanque B', lineas[1])
        self.assertEqual(ProductoProduccion.objects.count(), 0)

    def test_un_producto_planeado_de_otra_planeacion_tumba_el_lote(self):
        """El eslabón que ninguna clave foránea garantiza. La otra línea del mismo envío
        es válida y tampoco debe quedar escrita."""
        otra_planeacion = RegistroPlaneacion.objects.create(
            dom=self.dom, numero_registro=2, turno=self.turno, fecha_planeacion=FECHA,
        )
        pp_ajeno = ProductoPlaneacion.objects.create(
            registro_planeacion=otra_planeacion,
            dom_producto=self.producto_b,
            cantidad_proyectada=10,
        )

        respuesta = self.guardar(productos_produccion=[
            {'producto_planeacion': self.pp_a.id, 'cantidad_elaborada': 8},
            {'producto_planeacion': pp_ajeno.id, 'cantidad_elaborada': 5},
        ])

        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST, respuesta.data)
        self.assertIn('no pertenece a la planeación', respuesta.data['error'])
        self.assertEqual(
            ProductoProduccion.objects.count(), 0,
            'La línea válida del lote quedó escrita pese al rechazo de la otra.',
        )


class SinCantidadesTests(BaseAtomicoProduccion):
    """Un PUT sin `productos_produccion` tiene que seguir comportándose como siempre:
    el endpoint es el mismo que usan el resto de la pantalla y los guiones."""

    def test_un_put_sin_cantidades_guarda_el_registro(self):
        respuesta = self.guardar(novedad_cumplimiento_produccion='Sin novedades')

        self.assertEqual(respuesta.status_code, status.HTTP_200_OK, respuesta.data)
        self.jornada.refresh_from_db()
        self.assertEqual(self.jornada.novedad_cumplimiento_produccion, 'Sin novedades')
        self.assertEqual(ProductoProduccion.objects.count(), 0)
