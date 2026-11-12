"""예약 표를 읽고 쓰는 SQL.

예약이 있는지 찾는 일, 넣는 일, 지우는 일을 ORM 메서드 나열이 아니라
이 파일의 SQL 문장으로 처리한다.
사용자가 입력한 값은 문장에 이어 붙이지 않고 %s 자리 표시자로 넘긴다.

코드에서는 항상 %s를 쓴다.
SQLite에 연결하면 Django가 %s를 ?로 바꾸고, Supabase(PostgreSQL)는 %s를 그대로 쓴다.
"""

import datetime

from django.db import IntegrityError, connection, transaction
from django.utils import timezone


def _as_date_text(value):
    """읽어 온 날짜를 2026-11-13 글자로 맞춘다."""
    if isinstance(value, datetime.datetime):
        value = value.date()
    if isinstance(value, datetime.date):
        return value.isoformat()
    text = str(value).strip()
    # 날짜 뒤에 시각이 붙어 있으면 앞 10글자만 남긴다.
    return text[:10]


def _as_time_text(value):
    """읽어 온 시각을 09:00:00 글자로 맞춘다."""
    if isinstance(value, datetime.datetime):
        value = value.time()
    if isinstance(value, datetime.time):
        return f"{value.hour:02d}:{value.minute:02d}:{value.second:02d}"
    text = str(value).strip()
    # 09:00처럼 초가 없으면 초를 붙여 저장 형식과 같게 만든다.
    if len(text) == 5:
        return text + ":00"
    return text[:8]


def _normalize(row):
    """한 줄 딕셔너리의 날짜와 시각 형식을 화면이 기대하는 글자로 맞춘다."""
    if "id" in row and row["id"] is not None:
        row["id"] = int(row["id"])
    if "room_id" in row and row["room_id"] is not None:
        row["room_id"] = int(row["room_id"])
    if "date" in row and row["date"] is not None:
        row["date"] = _as_date_text(row["date"])
    if "start_time" in row and row["start_time"] is not None:
        row["start_time"] = _as_time_text(row["start_time"])
    return row


def _fetch_all(sql, params):
    """SELECT를 실행하고, 각 줄을 딕셔너리로 돌려준다.

    params는 SQL 안의 %s와 같은 순서로 나열한 값이다.
    값이 없는 조회도 빈 리스트를 넘겨, 나중에 값을 문장에 붙이지 않게 한다.
    """
    with connection.cursor() as cursor:
        # 두 번째 인자가 자리 표시자에 들어갈 값이다.
        cursor.execute(sql, params)
        # description은 결과 칸의 이름표다. SELECT가 아니면 None일 수 있다.
        if cursor.description is None:
            return []
        columns = []
        for column in cursor.description:
            columns.append(column[0])
        rows = []
        for raw_row in cursor.fetchall():
            # zip으로 칸 이름과 값을 짝지어 딕셔너리를 만든다.
            row = dict(zip(columns, raw_row))
            rows.append(_normalize(row))
        return rows


def _fetch_one(sql, params):
    """결과가 없으면 None, 있으면 첫 줄만 돌려준다."""
    rows = _fetch_all(sql, params)
    if len(rows) == 0:
        return None
    return rows[0]


def fetch_rooms():
    """시간표에 보여줄 방을 번호 순으로 가져온다.

    이 문장에는 사용자 입력이 없다.
    """
    sql = """
        SELECT
            "id" AS id,
            "name" AS name
        FROM "study_room"
        ORDER BY "id"
    """
    return _fetch_all(sql, [])


def fetch_room(room_id):
    """방 번호로 방 한 칸을 찾는다. 없으면 None이다."""
    sql = """
        SELECT
            "id" AS id,
            "name" AS name
        FROM "study_room"
        WHERE "id" = %s
    """
    # 리스트의 첫 값이 첫 번째 %s에 들어간다.
    return _fetch_one(sql, [room_id])


def fetch_reservations_for_date(date_text):
    """하루치 예약을 방 번호, 시작 시각 순으로 가져온다."""
    sql = """
        SELECT
            "reservation"."id" AS id,
            "reservation"."room_id" AS room_id,
            "study_room"."name" AS room_name,
            "reservation"."date" AS date,
            "reservation"."start_time" AS start_time,
            "reservation"."booker_name" AS booker_name,
            "reservation"."phone" AS phone,
            "reservation"."purpose" AS purpose,
            "reservation"."created_at" AS created_at
        FROM "reservation"
        JOIN "study_room" ON "study_room"."id" = "reservation"."room_id"
        WHERE "reservation"."date" = %s
        ORDER BY "study_room"."id", "reservation"."start_time"
    """
    return _fetch_all(sql, [date_text])


def fetch_reservations_between(start_text, end_text):
    """시작 날짜부터 끝 날짜까지 예약을 가져온다. 양 끝 날짜를 포함한다."""
    sql = """
        SELECT
            "reservation"."id" AS id,
            "reservation"."room_id" AS room_id,
            "study_room"."name" AS room_name,
            "reservation"."date" AS date,
            "reservation"."start_time" AS start_time,
            "reservation"."booker_name" AS booker_name,
            "reservation"."phone" AS phone,
            "reservation"."purpose" AS purpose,
            "reservation"."created_at" AS created_at
        FROM "reservation"
        JOIN "study_room" ON "study_room"."id" = "reservation"."room_id"
        WHERE "reservation"."date" >= %s
          AND "reservation"."date" <= %s
        ORDER BY "reservation"."date", "study_room"."id", "reservation"."start_time"
    """
    return _fetch_all(sql, [start_text, end_text])


def fetch_my_reservations(booker_name, phone):
    """이 이름과 전화번호로 저장된 예약을 날짜 순으로 가져온다.

    전화번호가 비어 있는 예전 줄은 이름이 같으면 함께 읽는다.
    다른 사람 줄이 섞였는지는 views.py가 다시 가린다.
    """
    sql = """
        SELECT
            "reservation"."id" AS id,
            "reservation"."room_id" AS room_id,
            "study_room"."name" AS room_name,
            "reservation"."date" AS date,
            "reservation"."start_time" AS start_time,
            "reservation"."booker_name" AS booker_name,
            "reservation"."phone" AS phone,
            "reservation"."purpose" AS purpose,
            "reservation"."created_at" AS created_at
        FROM "reservation"
        JOIN "study_room" ON "study_room"."id" = "reservation"."room_id"
        WHERE "reservation"."booker_name" = %s
          AND (
                "reservation"."phone" = %s
                OR "reservation"."phone" = ''
              )
        ORDER BY "reservation"."date", "reservation"."start_time", "study_room"."id"
    """
    return _fetch_all(sql, [booker_name, phone])


def fetch_reservation_for_slot(room_id, date_text, time_text):
    """같은 방, 같은 날짜, 같은 시작 시각의 예약이 있는지 찾는다.

    한 줄이라도 있으면 그 칸은 예약할 수 없다.
    제약 때문에 두 줄 이상이 되면 안 되지만, LIMIT 1로 한 줄만 읽는다.
    """
    sql = """
        SELECT
            "reservation"."id" AS id,
            "reservation"."room_id" AS room_id,
            "study_room"."name" AS room_name,
            "reservation"."date" AS date,
            "reservation"."start_time" AS start_time,
            "reservation"."booker_name" AS booker_name,
            "reservation"."phone" AS phone,
            "reservation"."purpose" AS purpose,
            "reservation"."created_at" AS created_at
        FROM "reservation"
        JOIN "study_room" ON "study_room"."id" = "reservation"."room_id"
        WHERE "reservation"."room_id" = %s
          AND "reservation"."date" = %s
          AND "reservation"."start_time" = %s
        LIMIT 1
    """
    # %s 세 개의 순서는 방 번호, 날짜, 시작 시각이다.
    return _fetch_one(sql, [room_id, date_text, time_text])


def fetch_reservation(reservation_id):
    """예약 번호로 예약 한 건을 찾는다. 없으면 None이다."""
    sql = """
        SELECT
            "reservation"."id" AS id,
            "reservation"."room_id" AS room_id,
            "study_room"."name" AS room_name,
            "reservation"."date" AS date,
            "reservation"."start_time" AS start_time,
            "reservation"."booker_name" AS booker_name,
            "reservation"."phone" AS phone,
            "reservation"."purpose" AS purpose,
            "reservation"."created_at" AS created_at
        FROM "reservation"
        JOIN "study_room" ON "study_room"."id" = "reservation"."room_id"
        WHERE "reservation"."id" = %s
    """
    return _fetch_one(sql, [reservation_id])


def insert_reservation(room_id, date_text, time_text, booker_name, phone, purpose):
    """예약 한 줄을 넣는다.

    phone은 하이픈을 뺀 숫자만 넘긴다. views.py가 검사한 뒤에 호출한다.
    성공하면 새 예약 번호를 돌려준다.
    같은 칸이 이미 있어서 데이터베이스가 거부하면 None을 돌려준다.
    이 함수는 확인 없이 바로 INSERT 한다. 거절은 표의 고유 제약이 한다.
    """
    # 지금 시각을 현재 데이터베이스가 받는 형식으로 바꾼다.
    # SQLite는 글자, Supabase는 시간 값으로 넘어간다.
    created_text = connection.ops.adapt_datetimefield_value(timezone.now())
    sql = """
        INSERT INTO "reservation" (
            "room_id",
            "date",
            "start_time",
            "booker_name",
            "phone",
            "purpose",
            "created_at"
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING "id"
    """
    params = [room_id, date_text, time_text, booker_name, phone, purpose, created_text]
    try:
        # atomic 안에서 오류가 나면 그 INSERT만 취소된다.
        # except를 atomic 안에 두면 Django가 거래를 깨진 상태로 본다.
        # 그래서 오류는 with 블록 밖에서 잡는다.
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                # RETURNING이 돌려준 첫 칸이 새 예약 번호다.
                # SQLite의 lastrowid는 Supabase에서 비어 있으므로 이 값을 쓴다.
                inserted = cursor.fetchone()
                new_id = inserted[0] if inserted else None
    except IntegrityError:
        # 고유 제약이 두 번째 예약을 거부하면 여기로 온다.
        return None
    if not new_id:
        return None
    return int(new_id)


def delete_reservation(reservation_id):
    """예약 한 줄을 지운다.

    이 함수는 호출되면 바로 지운다.
    주소를 열었을 때 호출하면 안 된다.
    views.py가 확인 버튼을 검사한 뒤에만 호출한다.
    지워진 줄 수를 돌려준다.
    """
    sql = """
        DELETE FROM "reservation"
        WHERE "id" = %s
    """
    with connection.cursor() as cursor:
        cursor.execute(sql, [reservation_id])
        # rowcount는 이번 DELETE가 지운 줄 수다.
        return cursor.rowcount
