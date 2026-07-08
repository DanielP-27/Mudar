# Generated for P: número de tratamiento fitosanitario como código de texto libre
# (antes IntegerField, con la "restricción de dígitos" del type=number). Mismo
# patrón que 0015_alter_dom_numero_factura.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('server', '0017_alter_dom_materiales_externos_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='registrotratamiento',
            name='numero_tratamiento',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Número de tratamiento termico fitosanitario asignado a este DOM'),
        ),
    ]
