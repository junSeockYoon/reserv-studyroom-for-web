"""브라우저 화면을 만드는 함수.

시간표, 예약 작성, 예약 확인과 취소를 처리한다.
날짜와 시간 규칙은 rules.py, 데이터베이스 읽기와 쓰기는 queries.py가 맡는다.
"""

import datetime

from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from . import queries, rules
from .models import Reservation

# 화면 문장. 코드 값은 주소나 조건에서 쓰고, 문장은 여기서만 고친다.
MESSAGES = {
    "bad_room": "선택한 스터디룸을 찾을 수 없습니다.",
    "bad_date": "날짜 형식이 올바르지 않습니다.",
    "bad_time": "시작 시간 형식이 올바르지 않습니다.",
    "past_date": "지난 날짜는 예약할 수 없습니다.",
    "past_time": "이미 시작한 시간은 예약할 수 없습니다.",
    "outside_hours": (
        "운영 시간은 09:00부터 21:00까지입니다. "
        "시작 시간은 09:00부터 20:00까지, 1시간 단위만 예약할 수 있습니다."
    ),
    "empty_name": "예약자 이름을 입력해 주세요.",
    "long_name": f"예약자 이름은 {Reservation.NAME_MAX}자 이하로 입력해 주세요.",
    "empty_purpose": "사용 목적을 입력해 주세요.",
    "long_purpose": f"사용 목적은 {Reservation.PURPOSE_MAX}자 이하로 입력해 주세요.",
    "taken": (
        "이 시간은 이미 예약되어 있습니다. "
        "같은 방, 같은 날짜, 같은 시작 시간은 한 명만 예약할 수 있어서 "
        "저장하지 않았습니다."
    ),
    "save_failed": "저장하지 못했습니다. 시간표에서 칸을 다시 선택해 주세요.",
    "missing_confirm": "확인 버튼을 누르기 전에는 예약이 취소되지 않습니다.",
    "cancel_failed": "예약을 취소하지 못했습니다. 다시 시도해 주세요.",
}

# 저장이나 취소 뒤에 주소로 전달하는 알림 코드.
# 사용자가 아무 글자나 넣어도, 여기 있는 문장만 화면에 나온다.
NOTICES = {
    "created": "예약이 저장되었습니다.",
    "cancelled": "예약이 취소되었습니다.",
}


def present_reservation(row):
    """SQL이 돌려준 한 줄에 화면용 날짜와 시간 글자를 더한다."""
    shown = dict(row)
    try:
        day = datetime.date.fromisoformat(shown["date"])
        shown["korean_date"] = rules.korean_date(day)
        shown["date_iso"] = day.isoformat()
    except (TypeError, ValueError):
        shown["korean_date"] = str(shown.get("date", ""))
        shown["date_iso"] = str(shown.get("date", ""))
    try:
        start = datetime.time.fromisoformat(shown["start_time"])
        shown["slot_label"] = rules.slot_label(start)
    except (TypeError, ValueError):
        shown["slot_label"] = str(shown.get("start_time", ""))
    shown["created_label"] = rules.stored_datetime_as_seoul(shown.get("created_at"))
    return shown


def build_board(day):
    """한 날짜의 방마다 12개 시간 칸을 만든다.

    예약이 없는 방도 시간표에 나와야 해서, 방 목록과 예약 목록을 따로 읽는다.
    """
    rooms = queries.fetch_rooms()
    reservations = queries.fetch_reservations_for_date(day.isoformat())
    # (방 번호, 시작 시각)으로 예약을 빨리 찾는다.
    by_slot = {}
    for row in reservations:
        by_slot[(row["room_id"], row["start_time"])] = row

    room_blocks = []
    past_time_count = 0
    for room in rooms:
        slots = []
        for start in rules.allowed_starts():
            time_text = rules.time_text(start)
            reservation = by_slot.get((room["id"], time_text))
            # 이 칸을 새로 예약하면 안 되는 이유. 없으면 None이다.
            closed = rules.calendar_block(day, start)
            if closed == "past_time":
                past_time_count = past_time_count + 1
            slots.append(
                {
                    "label": rules.slot_label(start),
                    "start_hm": f"{start.hour:02d}:{start.minute:02d}",
                    "reservation": reservation,
                    "closed": closed,
                }
            )
        room_blocks.append({"room": room, "slots": slots})

    shown_reservations = []
    for row in reservations:
        shown_reservations.append(present_reservation(row))
    return room_blocks, shown_reservations, past_time_count


@require_http_methods(["GET"])
def schedule(request):
    """첫 화면. 날짜를 고르면 그 날짜의 시간 칸을 보여 준다."""
    raw_date = request.GET.get("date", "")
    date_error = ""
    if raw_date.strip() == "":
        # 날짜를 주지 않으면 한국 시간 기준 오늘을 보여 준다.
        day = rules.local_today()
    else:
        parsed, code = rules.parse_date(raw_date)
        if code is not None:
            day = rules.local_today()
            date_error = MESSAGES["bad_date"] + " 오늘은 아래 시간표로 보여 드립니다."
        else:
            day = parsed

    room_blocks, reservations, past_time_count = build_board(day)
    notice_code = request.GET.get("notice", "")
    context = {
        "date_iso": day.isoformat(),
        "korean_date": rules.korean_date(day),
        "date_error": date_error,
        "is_past_day": day < rules.local_today(),
        "show_past_time_note": past_time_count > 0,
        "notice": NOTICES.get(notice_code, ""),
        "room_blocks": room_blocks,
        "reservations": reservations,
    }
    return render(request, "reservations/schedule.html", context)


def _submitted(request, key):
    """저장은 POST, 칸을 여는 주소는 GET이라 같은 이름을 양쪽에서 읽는다."""
    if request.method == "POST":
        return request.POST.get(key, "")
    return request.GET.get(key, "")


def _parse_room_id(text):
    """방 번호 글자를 정수로 바꾼다. 정수가 아니면 None이다."""
    try:
        return int(str(text).strip())
    except (TypeError, ValueError):
        return None


def _field_errors(name, purpose):
    """이름과 목적을 검사한다.

    앞뒤 공백은 없는 것으로 본다.
    돌려주는 값은 (저장할 이름, 저장할 목적, 오류 문장 리스트)이다.
    """
    cleaned_name = name.strip()
    cleaned_purpose = purpose.strip()
    errors = []
    if cleaned_name == "":
        errors.append(MESSAGES["empty_name"])
    elif len(cleaned_name) > Reservation.NAME_MAX:
        errors.append(MESSAGES["long_name"])
    if cleaned_purpose == "":
        errors.append(MESSAGES["empty_purpose"])
    elif len(cleaned_purpose) > Reservation.PURPOSE_MAX:
        errors.append(MESSAGES["long_purpose"])
    return cleaned_name, cleaned_purpose, errors


@require_http_methods(["GET", "POST"])
def reserve(request):
    """빈 칸에서 연 예약 폼. GET은 폼을 보여주고, POST는 저장을 시도한다."""
    room_id = _parse_room_id(_submitted(request, "room_id"))
    day, date_code = rules.parse_date(_submitted(request, "date"))
    start, start_code = rules.parse_start(_submitted(request, "start_time"))
    entered_name = _submitted(request, "booker_name")
    entered_purpose = _submitted(request, "purpose")

    # 칸 자체가 잘못된 이유를 먼저 모은다. 이름 검사보다 앞이다.
    slot_code = None
    room = None
    if room_id is None:
        slot_code = "bad_room"
    else:
        room = queries.fetch_room(room_id)
        if room is None:
            slot_code = "bad_room"
    if slot_code is None and date_code is not None:
        slot_code = date_code
    if slot_code is None and start_code is not None:
        slot_code = start_code
    if slot_code is None:
        # 날짜와 시각 형식은 맞다. 지난 날인지, 오늘 지난 시간인지만 본다.
        slot_code = rules.calendar_block(day, start)

    summary = None
    # 지난 칸도 어떤 칸이었는지는 보여 준다. 예약 폼은 slot_code가 없을 때만 연다.
    if room is not None and day is not None and start is not None:
        if slot_code is None or slot_code in ("past_date", "past_time"):
            summary = {
                "room_id": room["id"],
                "room_name": room["name"],
                "date_iso": day.isoformat(),
                "korean_date": rules.korean_date(day),
                "slot_label": rules.slot_label(start),
                "start_hm": f"{start.hour:02d}:{start.minute:02d}",
            }

    taken = None
    if slot_code is None and summary is not None:
        # 저장하기 전에 같은 칸이 있는지 SQL로 확인한다.
        taken = queries.fetch_reservation_for_slot(
            summary["room_id"],
            summary["date_iso"],
            rules.time_text(start),
        )

    field_errors = []
    save_error = ""
    if request.method == "POST" and slot_code is None and taken is None and summary is not None:
        cleaned_name, cleaned_purpose, field_errors = _field_errors(
            entered_name,
            entered_purpose,
        )
        if len(field_errors) == 0:
            new_id = queries.insert_reservation(
                summary["room_id"],
                summary["date_iso"],
                rules.time_text(start),
                cleaned_name,
                cleaned_purpose,
            )
            if new_id is None:
                # 확인과 저장 사이에 다른 저장이 들어왔거나, 제약이 거부했다.
                taken = queries.fetch_reservation_for_slot(
                    summary["room_id"],
                    summary["date_iso"],
                    rules.time_text(start),
                )
                if taken is None:
                    save_error = MESSAGES["save_failed"]
            else:
                # 저장 뒤 새로고침이 같은 저장을 다시 보내지 않도록 시간표로 보낸다.
                schedule_url = reverse("schedule")
                return redirect(
                    f"{schedule_url}?date={summary['date_iso']}&notice=created"
                )

    # 칸이 예약 가능하고, 아직 비어 있을 때만 입력 폼을 보여 준다.
    show_form = slot_code is None and taken is None and save_error == "" and summary is not None
    if summary is not None:
        back_date = summary["date_iso"]
    else:
        back_date = rules.local_today().isoformat()

    slot_message = ""
    if slot_code is not None:
        slot_message = MESSAGES.get(slot_code, MESSAGES["save_failed"])

    context = {
        "summary": summary,
        "slot_message": slot_message,
        "taken": None if taken is None else present_reservation(taken),
        "taken_message": MESSAGES["taken"] if taken is not None else "",
        "field_errors": field_errors,
        "save_error": save_error,
        "show_form": show_form,
        "booker_name": entered_name,
        "purpose": entered_purpose,
        "back_date": back_date,
        "name_max": Reservation.NAME_MAX,
        "purpose_max": Reservation.PURPOSE_MAX,
    }
    return render(request, "reservations/reserve.html", context)


@require_http_methods(["GET", "POST"])
def reservation_detail(request, reservation_id):
    """예약된 칸의 이름과 목적을 보여 주고, 확인 버튼이 있을 때만 취소한다.

    GET으로 이 함수에 들어와도 아래 POST 분기는 실행되지 않는다.
    주소를 열거나 새로고침하는 것만으로는 예약이 지워지지 않는다.
    """
    row = queries.fetch_reservation(reservation_id)
    if row is None:
        return render(
            request,
            "reservations/not_found.html",
            {"detail": "예약을 찾을 수 없습니다."},
            status=404,
        )
    shown = present_reservation(row)
    error = ""
    if request.method == "POST":
        # 숨은 입력 confirm이 yes일 때만 확인 버튼을 누른 것으로 본다.
        # 주소 뒤의 ?confirm=yes 는 POST 값이 아니라서 여기서 읽지 않는다.
        if request.POST.get("confirm") != "yes":
            error = MESSAGES["missing_confirm"]
        else:
            queries.delete_reservation(reservation_id)
            # 지운 뒤 다시 읽어서, 정말 없을 때만 취소되었다고 말한다.
            still_there = queries.fetch_reservation(reservation_id)
            if still_there is None:
                schedule_url = reverse("schedule")
                return redirect(
                    f"{schedule_url}?date={shown['date_iso']}&notice=cancelled"
                )
            error = MESSAGES["cancel_failed"]
    context = {
        "reservation": shown,
        "error": error,
    }
    return render(request, "reservations/detail.html", context)


@require_http_methods(["GET"])
def unknown_page(request, unused_path):
    """등록하지 않은 주소. 관리자 화면과 로그인 화면도 여기로 온다."""
    # unused_path는 주소 변환기가 요구하는 인자다. 화면에는 쓰지 않는다.
    del unused_path
    return render(
        request,
        "reservations/not_found.html",
        {"detail": "주소가 잘못되었습니다. 시간표에서 다시 선택해 주세요."},
        status=404,
    )
