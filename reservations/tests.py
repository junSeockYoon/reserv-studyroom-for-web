"""예약 규칙을 서버 없이 확인하는 테스트.

실행: python manage.py test
각 테스트는 끝나면 데이터를 되돌려, 다음 테스트와 섞이지 않는다.
"""

import datetime
from unittest.mock import patch

from django.test import TestCase

from reservations import queries, rules
from reservations.models import Reservation


class ReservationRulesTests(TestCase):
    """시간표, 저장, 중복, 취소가 약속대로 동작하는지 확인한다."""

    def setUp(self):
        # migrate가 넣어 둔 방 세 개를 이름으로 찾는다.
        self.room_ids = {}
        for room in queries.fetch_rooms():
            self.room_ids[room["name"]] = room["id"]

    def future_day(self, days=7):
        # 오늘로부터 며칠 뒤. 그 날짜는 12칸이 모두 예약 가능하다.
        return rules.local_today() + datetime.timedelta(days=days)

    def book(self, room_id, day, start="09:00", name="홍길동", purpose="팀 공부"):
        # 예약 폼과 같은 항목을 POST로 보낸다.
        return self.client.post(
            "/reserve/",
            {
                "room_id": str(room_id),
                "date": day.isoformat(),
                "start_time": start,
                "booker_name": name,
                "purpose": purpose,
            },
        )

    def test_three_rooms_and_empty_list(self):
        day = self.future_day()
        response = self.client.get(f"/?date={day.isoformat()}")
        self.assertContains(response, "룸 A")
        self.assertContains(response, "룸 B")
        self.assertContains(response, "룸 C")
        self.assertContains(response, "아직 예약이 없습니다")
        # 방 3개 x 칸 12개. 마지막 시작은 20:00이고 21:00 시작 칸은 없다.
        # 20:00~21:00은 보이는 글자와 스크린 리더용 이름에 각각 한 번씩 있다.
        self.assertContains(response, "비어 있음", count=36)
        self.assertContains(response, "20:00~21:00", count=6)
        self.assertNotContains(response, "21:00~22:00")
        self.assertNotContains(response, "08:00~09:00")

    def test_create_then_reject_duplicate_and_allow_other_room(self):
        day = self.future_day()
        room_a = self.room_ids["룸 A"]
        room_b = self.room_ids["룸 B"]

        first = self.book(room_a, day, name="홍길동", purpose="파이썬 공부")
        self.assertEqual(first.status_code, 302)
        schedule = self.client.get(first["Location"])
        self.assertContains(schedule, "예약이 저장되었습니다.")
        self.assertContains(schedule, "홍길동")
        self.assertContains(schedule, "예약됨", count=1)
        self.assertContains(schedule, "비어 있음", count=35)

        # 같은 칸을 다시 저장하면 폼 없이 이유를 보여 주고, 줄은 하나다.
        second = self.book(room_a, day, name="김철수", purpose="다른 모임")
        self.assertContains(second, "이미 예약되어 있습니다")
        self.assertContains(second, "저장하지 않았습니다")
        self.assertNotContains(second, "booker_name")
        self.assertEqual(len(queries.fetch_reservations_for_date(day.isoformat())), 1)

        # 같은 시각이라도 방이 다르면 예약할 수 있다.
        other = self.book(room_b, day, name="김철수", purpose="다른 모임")
        self.assertEqual(other.status_code, 302)
        self.assertEqual(len(queries.fetch_reservations_for_date(day.isoformat())), 2)

        # SQL로 넣은 줄을 Django 모델로도 읽을 수 있어야 한다.
        row = queries.fetch_reservation_for_slot(room_a, day.isoformat(), "09:00:00")
        saved = Reservation.objects.get(pk=row["id"])
        self.assertEqual(saved.booker_name, "홍길동")
        self.assertEqual(saved.purpose, "파이썬 공부")
        self.assertEqual(saved.date, day)
        self.assertEqual(saved.start_time, datetime.time(9, 0))
        self.assertIsNotNone(saved.created_at)

    def test_database_constraint_blocks_second_insert(self):
        # 화면의 사전 확인을 건너뛰고 INSERT를 두 번 호출한다.
        # 두 번째는 고유 제약이 거부해서 None이 되고, 줄은 하나여야 한다.
        day = self.future_day(8)
        room_id = self.room_ids["룸 A"]
        date_text = day.isoformat()
        first_id = queries.insert_reservation(
            room_id, date_text, "10:00:00", "이몽룡", "과제"
        )
        second_id = queries.insert_reservation(
            room_id, date_text, "10:00:00", "성춘향", "다른 과제"
        )
        self.assertIsNotNone(first_id)
        self.assertIsNone(second_id)
        self.assertEqual(len(queries.fetch_reservations_for_date(date_text)), 1)
        kept = queries.fetch_reservations_for_date(date_text)[0]
        self.assertEqual(kept["booker_name"], "이몽룡")

    def test_special_characters_stay_text(self):
        # 따옴표, 퍼센트, HTML이 값이 아니라 SQL이나 태그로 실행되지 않는지 본다.
        day = self.future_day(9)
        # 이름은 30자 제한 안에 두되, 따옴표와 SQL처럼 보이는 글자를 넣는다.
        weird_name = "홍길동'; DROP TABLE x;--"
        weird_purpose = "진도 100% <script>alert(1)</script>"
        response = self.book(
            self.room_ids["룸 C"],
            day,
            name=weird_name,
            purpose=weird_purpose,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(queries.fetch_rooms()), 3)
        row = queries.fetch_reservations_for_date(day.isoformat())[0]
        self.assertEqual(row["booker_name"], weird_name)
        self.assertEqual(row["purpose"], weird_purpose)
        detail = self.client.get(f"/reservations/{row['id']}/")
        self.assertContains(detail, "&lt;script&gt;")
        self.assertNotContains(detail, "<script>alert")

    def test_blank_and_too_long_input_is_not_saved(self):
        day = self.future_day(10)
        room_id = self.room_ids["룸 A"]
        blank = self.book(room_id, day, name="   ", purpose="   ")
        self.assertContains(blank, "예약자 이름을 입력해 주세요.")
        self.assertContains(blank, "사용 목적을 입력해 주세요.")
        self.assertContains(blank, "booker_name")
        self.assertEqual(len(queries.fetch_reservations_for_date(day.isoformat())), 0)

        long_name = self.book(room_id, day, name="가" * 31, purpose="공부")
        self.assertContains(long_name, "30자 이하")
        long_purpose = self.book(room_id, day, name="홍길동", purpose="나" * 101)
        self.assertContains(long_purpose, "100자 이하")
        self.assertEqual(len(queries.fetch_reservations_for_date(day.isoformat())), 0)

        # 제한과 같은 길이는 저장된다.
        accepted = self.book(room_id, day, name="가" * 30, purpose="나" * 100)
        self.assertEqual(accepted.status_code, 302)
        self.assertEqual(len(queries.fetch_reservations_for_date(day.isoformat())), 1)

    def test_past_date_and_outside_hours_are_rejected(self):
        room_id = self.room_ids["룸 A"]
        yesterday = rules.local_today() - datetime.timedelta(days=1)
        schedule = self.client.get(f"/?date={yesterday.isoformat()}")
        self.assertContains(schedule, "지난 날짜는 예약할 수 없습니다")
        self.assertNotContains(schedule, "비어 있음")

        past = self.client.get(
            f"/reserve/?room_id={room_id}&date={yesterday.isoformat()}&start_time=10:00"
        )
        self.assertContains(past, "지난 날짜는 예약할 수 없습니다.")
        self.assertNotContains(past, "booker_name")

        day = self.future_day(11)
        for start in ("08:00", "21:00", "09:30"):
            response = self.client.post(
                "/reserve/",
                {
                    "room_id": str(room_id),
                    "date": day.isoformat(),
                    "start_time": start,
                    "booker_name": "홍길동",
                    "purpose": "공부",
                },
            )
            self.assertContains(response, "운영 시간은 09:00부터 21:00까지입니다")
        bad_clock = self.client.get(
            f"/reserve/?room_id={room_id}&date={day.isoformat()}&start_time=아침"
        )
        self.assertContains(bad_clock, "시작 시간 형식이 올바르지 않습니다.")
        missing_room = self.client.get(
            f"/reserve/?room_id=9999&date={day.isoformat()}&start_time=09:00"
        )
        self.assertContains(missing_room, "선택한 스터디룸을 찾을 수 없습니다.")
        bad_date = self.client.get("/?date=2026-13-40")
        self.assertContains(bad_date, "날짜 형식이 올바르지 않습니다.")
        self.assertEqual(len(queries.fetch_reservations_for_date(day.isoformat())), 0)

    def test_today_past_hour_is_closed_and_later_hour_is_open(self):
        # 2026-11-12 13:37로 시계를 고정한다. 13:00 칸은 지났고 14:00 칸은 남아 있다.
        fixed = datetime.datetime(
            2026, 11, 12, 13, 37, tzinfo=datetime.timezone(datetime.timedelta(hours=9))
        )
        room_id = self.room_ids["룸 A"]
        with patch("reservations.rules.local_now", return_value=fixed):
            schedule = self.client.get("/?date=2026-11-12")
            self.assertContains(schedule, "지난 시간", count=15)
            self.assertContains(schedule, "비어 있음", count=21)
            too_late = self.client.post(
                "/reserve/",
                {
                    "room_id": str(room_id),
                    "date": "2026-11-12",
                    "start_time": "13:00",
                    "booker_name": "홍길동",
                    "purpose": "공부",
                },
            )
            self.assertContains(too_late, "이미 시작한 시간은 예약할 수 없습니다.")
            booked = self.client.post(
                "/reserve/",
                {
                    "room_id": str(room_id),
                    "date": "2026-11-12",
                    "start_time": "14:00",
                    "booker_name": "홍길동",
                    "purpose": "공부",
                },
            )
            self.assertEqual(booked.status_code, 302)
        self.assertEqual(len(queries.fetch_reservations_for_date("2026-11-12")), 1)

    def test_opening_the_address_does_not_cancel(self):
        day = self.future_day(12)
        self.book(self.room_ids["룸 B"], day, name="심사임당", purpose="독서")
        row = queries.fetch_reservations_for_date(day.isoformat())[0]
        url = f"/reservations/{row['id']}/"

        detail = self.client.get(url)
        self.assertContains(detail, "심사임당")
        self.assertContains(detail, "독서")
        self.assertContains(detail, "이 예약을 취소할까요?")
        self.assertContains(
            detail,
            "이 페이지 주소를 열거나 새로고침하는 것만으로는 취소되지 않습니다.",
        )
        self.assertContains(detail, "csrfmiddlewaretoken")

        # 주소 뒤에 확인 값을 붙여 GET 해도 지워지면 안 된다.
        self.client.get(url + "?confirm=yes")
        self.assertIsNotNone(queries.fetch_reservation(row["id"]))

        # 확인 값 없는 POST도 지워지면 안 된다.
        rejected = self.client.post(url, {})
        self.assertContains(rejected, "확인 버튼을 누르기 전에는 예약이 취소되지 않습니다.")
        self.assertIsNotNone(queries.fetch_reservation(row["id"]))

        cancelled = self.client.post(url, {"confirm": "yes"})
        self.assertEqual(cancelled.status_code, 302)
        self.assertIsNone(queries.fetch_reservation(row["id"]))
        follow = self.client.get(cancelled["Location"])
        self.assertContains(follow, "예약이 취소되었습니다.")
        self.assertContains(follow, "아직 예약이 없습니다")

    def test_missing_reservation_and_admin_are_not_found(self):
        missing = self.client.get("/reservations/999999/")
        self.assertContains(missing, "예약을 찾을 수 없습니다.", status_code=404)
        admin = self.client.get("/admin/")
        self.assertContains(admin, "페이지를 찾을 수 없습니다", status_code=404)
        login = self.client.get("/accounts/login/")
        self.assertEqual(login.status_code, 404)
