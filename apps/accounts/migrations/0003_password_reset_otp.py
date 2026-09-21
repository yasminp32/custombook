from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_passwordresettoken"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="passwordresettoken",
            name="reset_token",
        ),
        migrations.AddField(
            model_name="passwordresettoken",
            name="otp",
            field=models.CharField(default="", max_length=6),
            preserve_default=False,
        ),
    ]
