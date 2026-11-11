from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("conversations", "0002_alter_conversation_status"),
    ]

    operations = [
        migrations.AlterField(
            model_name="message",
            name="sender_type",
            field=models.CharField(
                choices=[
                    ("CUSTOMER", "Customer"),
                    ("AI", "AI"),
                    ("AGENT", "Agent"),
                    ("ADMIN", "Administrator"),
                    ("SYSTEM", "System"),
                ],
                max_length=20,
            ),
        ),
    ]
