"""예약 앱의 주소.

시간표, 예약 폼, 예약 확인이 각각 다른 주소다.
취소는 확인 화면과 같은 주소로 POST 할 때만 실행된다.
"""

from django.urls import path

from . import views

urlpatterns = [
    # http://127.0.0.1:8000/enter/  이름과 전화번호를 입력하는 문
    path("enter/", views.enter, name="enter"),
    # 나가기. 세션에 있던 이름과 전화번호를 지운다.
    path("leave/", views.leave, name="leave"),
    # http://127.0.0.1:8000/  방을 고르는 첫 화면
    path("", views.schedule, name="schedule"),
    # http://127.0.0.1:8000/rooms/1/?date=2026-11-13
    path("rooms/<int:room_id>/", views.room_schedule, name="room"),
    # http://127.0.0.1:8000/mine/  내 예약만 모은 목록
    path("mine/", views.mine, name="mine"),
    # http://127.0.0.1:8000/reserve/?room_id=1&date=2026-11-13&start_time=09:00
    path("reserve/", views.reserve, name="reserve"),
    # http://127.0.0.1:8000/reservations/1/
    path(
        "reservations/<int:reservation_id>/",
        views.reservation_detail,
        name="reservation_detail",
    ),
    # 위에서 맞지 않은 주소는 전부 여기로 온다. /admin/ 도 포함된다.
    path("<path:unused_path>", views.unknown_page),
]
