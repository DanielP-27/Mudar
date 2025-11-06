from rest_framework.decorators import api_view
from rest_framework.response import Response
from .serializers import UserSerializer, DomSerializer
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework import status
from django.shortcuts import get_object_or_404
from rest_framework.decorators import authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication


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