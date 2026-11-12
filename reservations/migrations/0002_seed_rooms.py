"""두 번째 데이터베이스 변경.

이미 만들어진 study_room 표에 룸 A, 룸 B, 룸 C를 넣는다.
예약이 겹치는지는 이 파일에서 검사하지 않는다.
겹침을 막는 SQL은 queries.py에 있고, 표 제약은 0001_initial.py에 있다.
"""

from django.db import migrations

# 화면에 미리 보여 줄 방 이름. 순서가 시간표의 위아래 순서가 된다.
ROOM_NAMES = ["룸 A", "룸 B", "룸 C"]


def create_rooms(apps, schema_editor):
    """방이 없으면 세 개를 만든다. 이미 있으면 또 만들지 않는다."""
    # 마이그레이션 안에서는 지금 모델 대신, 그 시점의 모델을 꺼내 쓴다.
    Room = apps.get_model("reservations", "Room")
    for name in ROOM_NAMES:
        # name이 같은 줄이 있으면 가져오고, 없으면 새로 만든다.
        Room.objects.get_or_create(name=name)


def remove_rooms(apps, schema_editor):
    """이 변경을 되돌릴 때 세 방만 지운다."""
    Room = apps.get_model("reservations", "Room")
    Room.objects.filter(name__in=ROOM_NAMES).delete()


class Migration(migrations.Migration):
    # 0001이 표를 만든 뒤에 이 파일을 실행한다.
    dependencies = [
        ("reservations", "0001_initial"),
    ]

    operations = [
        # 첫 함수는 적용할 때, 둘째 함수는 되돌릴 때 실행된다.
        migrations.RunPython(create_rooms, remove_rooms),
    ]
