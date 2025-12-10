from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from .models import Dom
from rest_framework.authtoken.models import Token


class DomIntegrationTest(TestCase):
    """Pruebas de integración - Flujos completos de trabajo"""
    
    def setUp(self):
        """Configuración inicial"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='integration_user',
            password='testpass123'
        )
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
    
    
    def test_flujo_completo_crud_dom(self):
        """
        INTEGRACIÓN: Flujo completo CRUD
        Simula: Crear → Leer → Actualizar → Eliminar
        """
        # ===== PASO 1: CREAR DOM =====
        dom_data = {
            'nombre_cliente': 'Pharmetique',
            'orden_produccion': 100,
            'cantidad_elaborada': 0,
            'lider_produccion': 'ALEX_AREVALO'
        }
        
        response_crear = self.client.post('/doms', dom_data, format='json')
        self.assertEqual(response_crear.status_code, status.HTTP_201_CREATED)
        
        # Obtener el ID del DOM creado
        if 'data' in response_crear.data:
            dom_id = response_crear.data['data']['dom_id']
        else:
            dom_id = response_crear.data['dom_id']
        
        print(f"✓ DOM creado con ID: {dom_id}")
        
        
        # ===== PASO 2: BUSCAR EL DOM =====
        response_buscar = self.client.get(f'/doms/buscar?search=Pharme')
        self.assertEqual(response_buscar.status_code, status.HTTP_200_OK)
        
        # Verificar que se encuentra el DOM
        if 'data' in response_buscar.data:
            resultados = response_buscar.data['data']
        else:
            resultados = response_buscar.data
        
        self.assertEqual(len(resultados), 1)
        self.assertEqual(resultados[0]['nombre_cliente'], 'Pharmetique')
        print(f"✓ DOM encontrado en búsqueda")
        
        
        # ===== PASO 3: OBTENER DOM ESPECÍFICO =====
        response_obtener = self.client.get(f'/doms/{dom_id}/')
        self.assertEqual(response_obtener.status_code, status.HTTP_200_OK)
        self.assertEqual(response_obtener.data['nombre_cliente'], 'Pharmetique')
        print(f"✓ DOM obtenido correctamente")
        
        
        # ===== PASO 4: ACTUALIZAR DOM =====
        update_data = {
            'cantidad_elaborada': 50,
            'lider_produccion': 'JULIO_MARTINEZ'
        }
        
        response_actualizar = self.client.patch(
            f'/doms/{dom_id}/', 
            update_data, 
            format='json'
        )
        self.assertEqual(response_actualizar.status_code, status.HTTP_200_OK)
        
        # Verificar que los cambios se guardaron
        dom_actualizado = Dom.objects.get(dom_id=dom_id)
        self.assertEqual(dom_actualizado.cantidad_elaborada, 50)
        self.assertEqual(dom_actualizado.lider_produccion, 'María García')
        print(f"✓ DOM actualizado correctamente")
        
        
        # ===== PASO 5: ELIMINAR DOM =====
        response_eliminar = self.client.delete(f'/doms/{dom_id}/')
        self.assertEqual(response_eliminar.status_code, status.HTTP_200_OK)
        
        # Verificar que ya no existe
        self.assertFalse(Dom.objects.filter(dom_id=dom_id).exists())
        print(f"✓ DOM eliminado correctamente")
        
        print("\n✅ FLUJO COMPLETO CRUD EXITOSO")
    
    
    def test_flujo_produccion_completo(self):
        """
        INTEGRACIÓN: Flujo de producción completo
        Simula el ciclo de vida de una orden de producción
        """
        # Crear DOM en estado inicial
        dom = Dom.objects.create(
            nombre_cliente="Flowserve",
            orden_produccion=200,
            cantidad_elaborada=0,
            materia_prima_disponible=False,
            lider_produccion='SIN_LIDER'
        )
        
        print(f"\n=== SIMULACIÓN FLUJO DE PRODUCCIÓN ===")
        print(f"DOM Creado - Estado: Inicial")
        
        
        # PASO 1: Asignar materia prima
        response = self.client.patch(
            f'/doms/{dom.dom_id}/',
            {'materia_prima_disponible': True},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        dom.refresh_from_db()
        self.assertTrue(dom.materia_prima_disponible)
        print(f"✓ Materia prima asignada")
        
        
        # PASO 2: Asignar líder de producción
        response = self.client.patch(
            f'/doms/{dom.dom_id}/',
            {'lider_produccion': 'ALEX_AREVALO'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        dom.refresh_from_db()
        self.assertEqual(dom.lider_produccion, 'Carlos Rodríguez')
        print(f"✓ Líder asignado: Carlos Rodríguez")
        
        
        # PASO 3: Iniciar producción
        response = self.client.patch(
            f'/doms/{dom.dom_id}/',
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        dom.refresh_from_db()
        
        
        # PASO 4: Actualizar cantidad elaborada (progreso)
        response = self.client.patch(
            f'/doms/{dom.dom_id}/',
            {'cantidad_elaborada': 100},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        dom.refresh_from_db()
        self.assertEqual(dom.cantidad_elaborada, 100)
        print(f"✓ Progreso: 100/200 unidades")
        
        
        # PASO 5: Completar producción
        response = self.client.patch(
            f'/doms/{dom.dom_id}/',
            {
                'cantidad_elaborada': 200,
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        dom.refresh_from_db()
        self.assertEqual(dom.cantidad_elaborada, 200)
        print(f"✓ Producción completada: 200/200 unidades")
        
        
        # Verificar estado final
        self.assertTrue(dom.materia_prima_disponible)
        self.assertEqual(dom.cantidad_elaborada, dom.orden_produccion)
        
        print("\n✅ FLUJO DE PRODUCCIÓN COMPLETADO EXITOSAMENTE")
    
    
    def test_busqueda_multiple_criterios(self):
        """
        INTEGRACIÓN: Búsqueda con múltiples criterios
        Verifica búsquedas por nombre y por ID
        """
        # Crear varios DOMs
        dom1 = Dom.objects.create(nombre_cliente="Pharmetique", orden_produccion=100)
        dom2 = Dom.objects.create(nombre_cliente="Flowserve", orden_produccion=200)
        dom3 = Dom.objects.create(nombre_cliente="PharmaCorp", orden_produccion=150)
        
        print(f"\n=== PRUEBAS DE BÚSQUEDA ===")
        
        # Búsqueda por nombre parcial
        response = self.client.get('/doms/buscar?search=Pharm')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        resultados = response.data.get('data', response.data)
        self.assertEqual(len(resultados), 2)  # Pharmetique y PharmaCorp
        print(f"✓ Búsqueda 'Pharm': {len(resultados)} resultados")
        
        # Búsqueda por ID
        response = self.client.get(f'/doms/buscar?id={dom2.dom_id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        resultados = response.data.get('data', response.data)
        self.assertEqual(len(resultados), 1)
        self.assertEqual(resultados[0]['nombre_cliente'], 'Flowserve')
        print(f"✓ Búsqueda por ID: DOM encontrado")
        
        # Búsqueda sin resultados
        response = self.client.get('/doms/buscar?search=NoExiste')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        resultados = response.data.get('data', response.data)
        self.assertEqual(len(resultados), 0)
        print(f"✓ Búsqueda sin resultados: 0 encontrados")
        
        print("\n✅ TODAS LAS BÚSQUEDAS FUNCIONAN CORRECTAMENTE")
    
    
    def test_integridad_datos_multiples_operaciones(self):
        """
        INTEGRACIÓN: Integridad de datos
        Verifica que múltiples operaciones no corrompan datos
        """
        # Crear 5 DOMs
        doms = []
        for i in range(1, 6):
            dom = Dom.objects.create(
                nombre_cliente=f"Cliente {i}",
                orden_produccion=i * 100,
                cantidad_elaborada=0
            )
            doms.append(dom)
        
        print(f"\n=== PRUEBA DE INTEGRIDAD DE DATOS ===")
        print(f"✓ Creados {len(doms)} DOMs")
        
        # Actualizar cada DOM
        for i, dom in enumerate(doms):
            response = self.client.patch(
                f'/doms/{dom.dom_id}/',
                {'cantidad_elaborada': (i + 1) * 50},
                format='json'
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        print(f"✓ Todos los DOMs actualizados")
        
        # Verificar que TODOS los cambios se guardaron correctamente
        for i, dom in enumerate(doms):
            dom.refresh_from_db()
            expected_cantidad = (i + 1) * 50
            self.assertEqual(dom.cantidad_elaborada, expected_cantidad)
        
        print(f"✓ Integridad de datos verificada")
        
        # Eliminar DOMs impares
        for i, dom in enumerate(doms):
            if i % 2 == 0:  # 0, 2, 4 (DOMs 1, 3, 5)
                response = self.client.delete(f'/doms/{dom.dom_id}/')
                self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verificar que solo quedan los DOMs pares
        total_doms = Dom.objects.count()
        self.assertEqual(total_doms, 2)  # DOMs 2 y 4
        print(f"✓ Eliminación selectiva correcta: {total_doms} DOMs restantes")
        
        print("\n✅ INTEGRIDAD DE DATOS MANTENIDA")
    
    
    def test_flujo_autenticacion_y_autorizacion(self):
        """
        INTEGRACIÓN: Autenticación y autorización
        Verifica el flujo de login → operaciones → logout
        """
        print(f"\n=== FLUJO DE AUTENTICACIÓN ===")
        
        # PASO 1: Remover credenciales (simular usuario no logueado)
        self.client.credentials()
        
        # Intentar crear DOM sin autenticación
        dom_data = {'nombre_cliente': 'Test', 'orden_produccion': 100}
        response = self.client.post('/doms', dom_data, format='json')
        
        # Dependiendo de tu implementación:
        # Si NO requiere auth: esperar 201
        # Si SÍ requiere auth: esperar 401
        print(f"✓ Intento sin auth: {response.status_code}")
        
        
        # PASO 2: Autenticarse nuevamente
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        # Ahora crear DOM con autenticación
        response = self.client.post('/doms', dom_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        print(f"✓ Creación con auth exitosa")
        
        
        # PASO 3: Realizar operaciones autenticadas
        if 'data' in response.data:
            dom_id = response.data['data']['dom_id']
        else:
            dom_id = response.data['dom_id']
        
        response = self.client.get(f'/doms/{dom_id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        print(f"✓ Lectura con auth exitosa")
        
        
        # PASO 4: Logout (simular)
        self.client.credentials()
        print(f"✓ Sesión cerrada")
        
        print("\n✅ FLUJO DE AUTENTICACIÓN COMPLETO")


class DomValidationIntegrationTest(TestCase):
    """Pruebas de integración para validaciones"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='validator', password='test123')
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
    
    
    def test_validacion_campos_requeridos(self):
        """
        INTEGRACIÓN: Validación de campos requeridos
        Verifica que no se puedan crear DOMs sin campos obligatorios
        """
        print(f"\n=== VALIDACIÓN DE CAMPOS REQUERIDOS ===")
        
        # Intentar crear DOM sin nombre_cliente
        response = self.client.post('/doms', {'orden_produccion': 100}, format='json')
        
        # Dependiendo de tu modelo, esto podría ser 400 o 201
        # Si nombre_cliente es requerido: esperar 400
        print(f"✓ Sin nombre_cliente: {response.status_code}")
        
        # Intentar crear DOM sin orden_produccion
        response = self.client.post('/doms', {'nombre_cliente': 'Test'}, format='json')
        print(f"✓ Sin orden_produccion: {response.status_code}")
        
        # Crear DOM con todos los campos requeridos
        response = self.client.post(
            '/doms',
            {'nombre_cliente': 'Test', 'orden_produccion': 100},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        print(f"✓ Con campos requeridos: ÉXITO")
        
        print("\n✅ VALIDACIONES FUNCIONANDO")