from django.apps import AppConfig


class ReservationsConfig(AppConfig):
    """예약 앱의 이름표.

    settings.py의 INSTALLED_APPS에 이 클래스를 적으면
    Django가 reservations 폴더를 앱으로 인식한다.
    """

    # 번호를 저장하는 칸의 기본 종류. models.py의 id와 같다.
    default_auto_field = "django.db.models.BigAutoField"
    # 이 앱이 들어 있는 파이썬 패키지 이름.
    name = "reservations"
    # 사람에게 보여줄 이름. 관리자 화면은 없지만 앱의 이름으로 남긴다.
    verbose_name = "스터디룸 예약"
