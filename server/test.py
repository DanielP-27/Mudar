from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from .models import Dom
from rest_framework.authtoken.models import Token

class DomModelTest(TestCase):
    """Pruebas unitarias del modelo Dom"""
    
    def setUp(self):
        """Configuración inicial para cada prueba"""
        self.dom = Dom.objects.create(
            nombre_cliente="Test Cliente",
            orden_produccion=100,
            cantidad_elaborada=50
        )
    
    def test_crear_dom(self):
        """Prueba que se puede crear un DOM correctamente"""
        self.assertEqual(self.dom.nombre_cliente, "Test Cliente")
        self.assertEqual(self.dom.orden_produccion, 100)
        self.assertIsNotNone(self.dom.dom_id)
    
    def test_str_dom(self):
        """Prueba el método __str__ del modelo"""
        expected = f"Dom {self.dom.dom_id} - Test Cliente"
        self.assertEqual(str(self.dom), expected)
    
    def test_campos_opcionales_vacios(self):
        """Prueba que los campos opcionales pueden estar vacíos"""
        dom = Dom.objects.create(nombre_cliente="Cliente Simple")
        self.assertEqual(dom.lider_produccion, 'SIN_LIDER')
        self.assertFalse(dom.materia_prima_disponible)


class DomAPITest(TestCase):
    """Pruebas unitarias de los endpoints del API"""
    
    def setUp(self):
        """Configuración inicial con usuario autenticado"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        self.dom_data = {
            'nombre_cliente': 'Cliente Test API',
            'orden_produccion': 200,
            'cantidad_elaborada': 100
        }
    
    def test_crear_dom_autenticado(self):
        """Prueba crear DOM con usuario autenticado"""
        response = self.client.post('/doms', self.dom_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['success'])
    
    def test_crear_dom_sin_autenticacion(self):
        """Prueba crear DOM sin autenticación (debe fallar)"""
        self.client.credentials()  # Remover credenciales
        response = self.client.post('/doms', self.dom_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_obtener_dom_existente(self):
        """Prueba obtener un DOM que existe"""
        dom = Dom.objects.create(**self.dom_data)
        response = self.client.get(f'/doms/{dom.dom_id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['nombre_cliente'], 'Cliente Test API')
    
    def test_obtener_dom_inexistente(self):
        """Prueba obtener un DOM que no existe"""
        response = self.client.get('/doms/99999/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_actualizar_dom(self):
        """Prueba actualizar un DOM existente"""
        dom = Dom.objects.create(**self.dom_data)
        update_data = {'nombre_cliente': 'Cliente Actualizado'}
        response = self.client.patch(f'/doms/{dom.dom_id}/', update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        dom.refresh_from_db()
        self.assertEqual(dom.nombre_cliente, 'Cliente Actualizado')
    
    def test_eliminar_dom(self):
        """Prueba eliminar un DOM existente"""
        dom = Dom.objects.create(**self.dom_data)
        dom_id = dom.dom_id
        response = self.client.delete(f'/doms/{dom_id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Dom.objects.filter(dom_id=dom_id).exists())
    
    def test_buscar_doms(self):
        """Prueba la funcionalidad de búsqueda"""
        Dom.objects.create(nombre_cliente="Pharmetique")
        Dom.objects.create(nombre_cliente="Flowserve")
        response = self.client.get('/doms/buscar?q=Pharme')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)