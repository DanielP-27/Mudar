Mudar de Colombia S.A.S. — Contexto del Proyecto
Descripción General
Aplicación web para la gestión de DOMs (Documentos Origen de Madera) que rastrea el ciclo de vida completo de producción: planeación, producción, tratamiento térmico, despachos y entregas.
Stack Tecnológico

Backend: Django REST Framework + PostgreSQL
Frontend: React + Vite (en construcción)
Autenticación: JWT (djangorestframework-simplejwt)


Arquitectura del Backend
Estructura de Módulos
El backend está organizado en módulos. Cada módulo sigue este patrón:
models.py → serializers.py → views.py → urls.py

Módulos
#MóduloEstado

1 Listas Predefinidas Validado
2 Gestión de DOMs Validado
3 Registro de Producción Validado
4 Registro de Planeación Validado
5 Cronómetro Validado6Dashboard / Reportes Validado

Convenciones Establecidas

Modelos

Todos los nombres de campo en snake_case
Todo modelo tiene verbose_name y ordering en la clase Meta
numero_registro es siempre auto-generado — nunca escribible vía API
dom FK es siempre asignado del lado del servidor — nunca escribible vía API
Los métodos save() personalizados no deben referenciar campos inexistentes

Serializers

Todos los campos del modelo deben estar listados explícitamente en fields
read_only_fields debe incluir siempre: numero_registro, dom
Los serializers anidados deben coincidir exactamente con la estructura del modelo relacionado
Las propiedades calculadas (tiempo_proyectado, cantidad_pendiente, sumatoria_tiempo_asignado_turnos, tiempo_restante_dia) dependen de que fecha_planeacion y cantidad_pedido estén presentes en fields

Vistas

select_related debe cubrir todas las FK usadas en el serializer
serializer.save() debe pasar todos los argumentos FK requeridos explícitamente (ej. dom=dom, productoDom=dom)
Se requiere un refresh con select_related antes del return Response cuando se retornan propiedades calculadas
Todas las vistas deben definir permission_classes
