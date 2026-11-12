"""데이터베이스 표의 설계도.

방 표와 예약 표의 칸 이름, 그리고 같은 칸을 두 번 저장하지 못하게 하는 제약을 적는다.
실제로 예약을 찾고 넣고 지우는 SQL은 queries.py에 있다.
이 파일의 모델만으로 예약 가능 여부를 판단하지 않는다.
"""

from django.db import models


class Room(models.Model):
    """스터디룸 한 칸.

    룸 A, 룸 B, 룸 C는 화면에서 사람이 추가하지 않는다.
    migrations/0002_seed_rooms.py가 처음 한 번 넣어 둔다.
    """

    # 각 방을 구분하는 번호. 1, 2, 3처럼 데이터베이스가 채운다.
    id = models.BigAutoField(primary_key=True)
    # 화면에 보여줄 이름. 같은 이름은 두 번 둘 수 없다.
    name = models.CharField("이름", max_length=20, unique=True, null=False)

    class Meta:
        # SQL에서 쓸 표 이름. 앱 이름을 붙인 긴 이름 대신 짧게 고정한다.
        db_table = "study_room"
        verbose_name = "스터디룸"
        verbose_name_plural = "스터디룸"

    def __str__(self):
        # 관리 화면은 없지만, 셸에서 방을 출력할 때 이름이 보이게 한다.
        return self.name


class Reservation(models.Model):
    """한 시간짜리 예약 한 건."""

    # 화면과 검사 코드가 함께 쓰는 글자 수 제한.
    # SQLite는 글자 수 제한을 스스로 지키지 않는다.
    # 그래서 views.py가 INSERT 하기 전에 이 숫자로 다시 검사한다.
    NAME_MAX = 30
    # 전화번호는 숫자만 저장한다. 01012345678처럼 최대 11자리다.
    PHONE_MAX = 20
    PURPOSE_MAX = 100

    id = models.BigAutoField(primary_key=True)
    # 어느 방의 예약인지. 예약이 남아 있는 방은 함부로 지울 수 없다.
    room = models.ForeignKey(
        Room,
        verbose_name="스터디룸",
        on_delete=models.PROTECT,
        related_name="reservations",
    )
    # 예약 날짜. 시간대 없이 달력 날짜만 저장한다.
    date = models.DateField("날짜", null=False)
    # 시작 시각. 09:00, 10:00, ... 20:00 중 하나다.
    start_time = models.TimeField("시작 시간", null=False)
    booker_name = models.CharField("예약자 이름", max_length=NAME_MAX, null=False)
    # 입장할 때 받은 전화번호. 하이픈을 뺀 숫자만 저장해서 같은 번호를 같은 사람으로 본다.
    phone = models.CharField("전화번호", max_length=PHONE_MAX, null=False)
    purpose = models.CharField("사용 목적", max_length=PURPOSE_MAX, null=False)
    # 저장 시각. 화면의 예약 조건에는 쓰이지 않고 기록으로만 남긴다.
    created_at = models.DateTimeField("예약한 시각", null=False)

    class Meta:
        db_table = "reservation"
        verbose_name = "예약"
        verbose_name_plural = "예약"
        constraints = [
            # 같은 방, 같은 날짜, 같은 시작 시간은 한 줄만 허용한다.
            # 화면에서 먼저 확인해도, 두 저장이 동시에 들어가면 둘 다 통과할 수 있다.
            # 그 경우에도 데이터베이스가 두 번째 줄을 거부하도록 표에 제약을 건다.
            models.UniqueConstraint(
                fields=["room", "date", "start_time"],
                name="one_reservation_per_slot",
            )
        ]

    def __str__(self):
        return f"{self.room} {self.date} {self.start_time} {self.booker_name}"
