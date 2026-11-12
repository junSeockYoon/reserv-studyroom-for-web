"""예약 표에 전화번호 칸을 추가한다.

이미 저장된 줄이 있으면 빈 문자열을 넣고, 그 기본값은 모델에는 남기지 않는다.
새로 저장하는 예약은 views.py가 검사한 전화번호만 넣는다.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reservations", "0002_seed_rooms"),
    ]

    operations = [
        migrations.AddField(
            model_name="reservation",
            name="phone",
            field=models.CharField(
                default="",
                max_length=20,
                verbose_name="전화번호",
            ),
            preserve_default=False,
        ),
    ]
