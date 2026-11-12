"""주소의 시작점.

브라우저가 요청한 경로를 reservations 앱의 주소 목록으로 넘긴다.
관리자 화면(/admin/)은 일부러 만들지 않는다.
"""

from django.urls import include, path

urlpatterns = [
    # 빈 주소부터 예약 앱이 처리한다.
    # reservations/urls.py 안에 시간표, 예약, 취소 주소가 있다.
    path("", include("reservations.urls")),
]
