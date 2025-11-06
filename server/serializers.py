from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Dom
from django.db import models

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email','password']

class DomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dom
        fields = '__all__'