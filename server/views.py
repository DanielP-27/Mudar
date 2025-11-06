from rest_framework.decorators import api_view
from rest_framework.response import Response
from .serializers import UserSerializer, DomSerializer
from .models import Dom
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework import status
from django.shortcuts import get_object_or_404
from rest_framework.decorators import authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from django.db.models import Q


# Vista de login 
@api_view(['POST'])
def login(request):

    user = get_object_or_404(User, username=request.data['username'])

    if not user.check_password(request.data['password']):
        return Response({"error": "Invalid Password"}, status=status.HTTP_400_BAD_REQUEST)

    token, created = Token.objects.get_or_create(user=user)
    serializer = UserSerializer(instance=user)
    return Response({"token": token.key, "user": serializer.data}, status=status.HTTP_200_OK)

# Vista registro nuevos usuarios
@api_view(['POST'])
def register(request):
    serializer = UserSerializer(data=request.data)

    if serializer.is_valid():
        serializer.save()
        user = User.objects.get(username=serializer.data['username'])
        user.set_password(serializer.data['password'])
        user.save()

        token = Token.objects.create(user = user)

        return Response({'token':token.key, "user":serializer.data}, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Vista token de autenticación
@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def profile(request):

    serializer = UserSerializer(instance=request.user)

    return Response(serializer.data, status=status.HTTP_200_OK)

    #return Response("You are login with {}".format(request.user.username), status=status.HTTP_200_OK)

# Vista de Logout
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    request.user.auth_token.delete()
    return Response({"message": "Logout successful"}, tatus=status.HTTP_200_OK )


# vista de creación dom's; por ahora, solo campo cliente obligatorio, es importante realizar las modificaciones necesarias para la entrega del producto final
@api_view(['POST'])
def crear_dom(request):

    # Conexión con serializer
    serializer = DomSerializer(data=request.data)
    
    # Validacion de los datos recibidos
    if serializer.is_valid():
    # si los datos son validos, guarda en DB
        dom = serializer.save()

        return Response(
            {
                'success': True,
                'message': 'Nuevo dom registrado exitosamente',
                'data': {
                    'dom_id': dom.dom_id,
                    'nombre_cliente': dom.nombre_cliente,
                    'dom_completo': serializer.data 
                }
            },
            status=status.HTTP_201_CREATED
    )

    # en caso que existan errores de validación
    return Response(
        {
            'sucess': False,
            'message': 'Error al registar nuevo Dom',
            'errors': serializer.errors
        },
        status=status.HTTP_400_BAD_REQUEST
    )

# Metodo para obtener DOMS x ID'S necesario para la actualización de los registros DOM
@api_view(['GET'])
def obtener_dom(request, dom_id):
    try:
        dom = Dom.objects.get(dom_id=dom_id)
        serializer = DomSerializer(dom)

        return Response(
            {
                'success': True,
                'data': serializer.data
            },
            status=status.HTTP_200_OK
        )
    except Dom.DomNotExist:
        return Response(
            {
                'success': False,
                'message': f'registro con id {dom_id} no encontrado'
            },
            status=status.HTTP_404_NOT_FOUND
        )
    
@api_view(['GET', 'PUT', 'PATCH'])
def dom_detail(request, dom_id):
    try:
        dom = Dom.objects.get(dom_id=dom_id)
    except Dom.DoesNotExist:
        return Response({'error': 'DOM no encontrado'}, status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'GET':
        serializer = DomSerializer(dom)
        return Response(serializer.data)
    
    elif request.method in ['PUT', 'PATCH']:
        serializer = DomSerializer(dom, data=request.data, partial=(request.method == 'PATCH'))
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
# Metodo para obtener DOM en barra de busqueda funcionalidad editat DOMS se admitirá busqueda x id o por nombre
@api_view(['GET'])
def buscar_doms(resquet):
    search_query = resquet.GET.get('search', '')
    dom_id = resquet.GET.get('id', '')

    doms = Dom.objects.all()

    # IF para realizar busqueda x id
    if dom_id:
        doms = doms.filter(dom_id=dom_id)
    # IF para realizar busqueda x nombre cliente
    if search_query:
        doms = doms.filter(nombre_cliente__icontains=search_query)
    
    serializer = DomSerializer(doms, many=True)

    return Response(
        {
            'success': True,
            'count': len(serializer.data),
            'data': serializer.data
        },
        status=status.HTTP_200_OK
    )

# Metódo para actualizar un DOM
@api_view(['PUT', 'PATCH'])
def actualizar_dom(request, dom_id):
    # PUT: actualización completa
    # PATCH: actualización parcial
    try:
        dom = Dom.objects.get(dom_id=dom_id)

        partial = request.method == 'PATCH'
        serializer = DomSerializer(dom, data=request.data, partial=partial )

        if serializer.is_valid():
            dom_actualizado = serializer.save()

            return Response (
                {
                    'success': True,
                    'message': 'Dom actualizado exitosamente',
                    'data': {
                        'dom_id': dom_actualizado.dom_id,
                        'nombre_cliente': dom_actualizado.nombre_cliente
                    }
                }, 
                status=status.HTTP_200_OK
            )
        return Response(
            {
                'success': False,
                'message': 'Error al actualizar el Dom',
                'errors': serializer.errors
            },
            satrus=status.HTTP_400_BAD_REQUEST
        )
    except Dom.DoesNotExist:
        return Response (
            {
                'success': False,
                'message': f'registro con id {dom_id} no encontrado'
            },
            status=status.HTTP_404_NOT_FOUND
        )
        