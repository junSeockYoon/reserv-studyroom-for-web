"""브라우저 화면을 만드는 함수.

시간표, 예약 작성, 예약 확인과 취소를 처리한다.
사이트에 들어가려면 먼저 이름과 전화번호를 입력한다.
예약 목록과 취소는 그 이름과 전화번호로 저장한 예약만 보여 준다.
날짜와 시간 규칙은 rules.py, 데이터베이스 읽기와 쓰기는 queries.py가 맡는다.
"""

import datetime
from functools import wraps
from urllib.parse import quote

from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from . import identity, queries, rules
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
    "empty_phone": "전화번호를 입력해 주세요.",
    "bad_phone": (
        "전화번호는 0으로 시작하는 10자리 또는 11자리 숫자로 입력해 주세요. "
        "하이픈은 있어도 됩니다."
    ),
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
    "not_mine": "본인 예약만 볼 수 있습니다.",
}

# 저장이나 취소 뒤에 주소로 전달하는 알림 코드.
# 사용자가 아무 글자나 넣어도, 여기 있는 문장만 화면에 나온다.
NOTICES = {
    "created": "예약이 저장되었습니다.",
    "cancelled": "예약이 취소되었습니다.",
}


def require_visitor(view_func):
    """이름과 전화번호가 없으면 입장 화면으로 보낸다.

    시간표, 예약, 취소 화면이 이 검사를 거친다.
    """

    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        visitor = identity.current_visitor(request)
        if visitor is None:
            target = request.get_full_path()
            # 입장 뒤에 원래 보려던 주소로 돌아오게 next에 붙인다.
            enter_url = reverse("enter")
            return redirect(f"{enter_url}?next={quote(target, safe='/?=&')}")
        request.visitor = visitor
        return view_func(request, *args, **kwargs)

    return wrapped


def safe_next(text):
    """입장 뒤에 이동할 주소. 이 사이트 안의 주소만 허용한다."""
    if text is None:
        return reverse("schedule")
    cleaned = str(text).strip()
    if cleaned == "" or not cleaned.startswith("/") or cleaned.startswith("//"):
        return reverse("schedule")
    if "\\" in cleaned:
        return reverse("schedule")
    return cleaned


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
    shown["phone_label"] = rules.format_phone(shown.get("phone", ""))
    shown["created_label"] = rules.stored_datetime_as_seoul(shown.get("created_at"))
    return shown


def _for_visitor(row, visitor):
    """내 예약은 내용을 그대로 두고, 다른 사람 예약은 개인 정보를 빼 둔다."""
    if identity.same_person(row, visitor):
        shown = present_reservation(row)
        shown["is_mine"] = True
        return shown
    try:
        day_text = datetime.date.fromisoformat(str(row["date"])).isoformat()
    except (TypeError, ValueError):
        day_text = str(row.get("date", ""))
    try:
        label = rules.slot_label(datetime.time.fromisoformat(str(row["start_time"])))
    except (TypeError, ValueError):
        label = ""
    # 이름, 전화번호, 목적은 여기 넣지 않는다. 화면 HTML에도 나가면 안 된다.
    return {
        "is_mine": False,
        "room_name": row["room_name"],
        "date_iso": day_text,
        "slot_label": label,
    }


def _taken_map(rows):
    """(방 번호, 날짜)마다 이미 예약된 시작 시각을 모은다."""
    taken = {}
    for row in rows:
        key = (row["room_id"], row["date"])
        if key not in taken:
            taken[key] = set()
        taken[key].add(row["start_time"])
    return taken


def open_count(day, room_id, taken):
    """그 날짜, 그 방에서 아직 예약할 수 있는 칸 수."""
    reserved = taken.get((room_id, day.isoformat()), set())
    count = 0
    for start in rules.allowed_starts():
        if rules.calendar_block(day, start) is not None:
            continue
        if rules.time_text(start) in reserved:
            continue
        count = count + 1
    return count


def describe_day(day, room_id, taken, selected):
    """날짜 칩에 넣을 요일, 날짜, 남은 칸 수."""
    count = open_count(day, room_id, taken)
    if day < rules.local_today():
        state = "past"
    elif count == 0:
        state = "full"
    else:
        state = "open"
    return {
        "iso": day.isoformat(),
        "day_num": day.day,
        "weekday": rules.weekday_char(day),
        "open_count": count,
        "state": state,
        "selected": selected is not None and day == selected,
    }


def coming_days(count, room_id, taken, selected):
    """오늘부터 count일 동안의 날짜 칩."""
    today = rules.local_today()
    days = []
    offset = 0
    while offset < count:
        day = today + datetime.timedelta(days=offset)
        days.append(describe_day(day, room_id, taken, selected))
        offset = offset + 1
    return days


def slots_for_room(day, room, rows, visitor):
    """한 방, 한 날짜의 12개 시간 칸."""
    by_time = {}
    for row in rows:
        if row["room_id"] != room["id"]:
            continue
        by_time[row["start_time"]] = _for_visitor(row, visitor)

    slots = []
    past_time_count = 0
    for start in rules.allowed_starts():
        time_text = rules.time_text(start)
        closed = rules.calendar_block(day, start)
        if closed == "past_time":
            past_time_count = past_time_count + 1
        slots.append(
            {
                "label": rules.slot_label(start),
                "start_hm": f"{start.hour:02d}:{start.minute:02d}",
                "reservation": by_time.get(time_text),
                "closed": closed,
            }
        )
    return slots, past_time_count


def _chosen_day(raw_date):
    """주소의 날짜를 읽는다. 없거나 잘못되면 오늘과 오류 문장을 돌려준다."""
    if raw_date.strip() == "":
        return rules.local_today(), ""
    parsed, code = rules.parse_date(raw_date)
    if code is not None:
        return rules.local_today(), MESSAGES["bad_date"] + " 오늘은 아래 시간표로 보여 드립니다."
    return parsed, ""


@require_http_methods(["GET", "POST"])
def enter(request):
    """사이트에 들어가기 전에 이름과 전화번호를 받는다."""
    if request.method == "POST":
        next_url = safe_next(request.POST.get("next"))
        name_value = request.POST.get("booker_name", "")
        phone_value = request.POST.get("phone", "")
    else:
        next_url = safe_next(request.GET.get("next"))
        name_value = ""
        phone_value = ""

    errors = []
    if request.method == "POST":
        cleaned_name, name_error = _clean_name(name_value)
        phone, phone_code = rules.normalize_phone(phone_value)
        if name_error != "":
            errors.append(name_error)
        if phone_code is not None:
            errors.append(MESSAGES[phone_code])
        if len(errors) == 0:
            identity.remember(request, cleaned_name, phone)
            return redirect(next_url)

    # 이미 들어온 사람이 이 화면을 다시 열면, 지금 값을 보여 주고 고칠 수 있게 한다.
    visitor = identity.current_visitor(request)
    if request.method == "GET" and visitor is not None:
        name_value = visitor["name"]
        phone_value = visitor["phone_label"]

    context = {
        "errors": errors,
        "booker_name": name_value,
        "phone": phone_value,
        "next_url": next_url,
        "name_max": Reservation.NAME_MAX,
    }
    return render(request, "reservations/enter.html", context)


@require_http_methods(["POST"])
def leave(request):
    """이 브라우저에 기억된 이름과 전화번호를 지우고 입장 화면으로 보낸다."""
    request.session.flush()
    return redirect("enter")


@require_visitor
@require_http_methods(["GET"])
def schedule(request):
    """첫 화면. 방을 고르고, 방마다 앞으로 7일의 남은 칸을 보여 준다."""
    today = rules.local_today()
    last = today + datetime.timedelta(days=6)
    taken = _taken_map(
        queries.fetch_reservations_between(today.isoformat(), last.isoformat())
    )
    room_cards = []
    for room in queries.fetch_rooms():
        days = coming_days(7, room["id"], taken, None)
        open_days = 0
        for day in days:
            if day["state"] == "open":
                open_days = open_days + 1
        room_cards.append(
            {
                "room": room,
                "days": days,
                "open_days": open_days,
            }
        )
    context = {
        "room_cards": room_cards,
        "notice": NOTICES.get(request.GET.get("notice", ""), ""),
    }
    return render(request, "reservations/schedule.html", context)


@require_visitor
@require_http_methods(["GET"])
def room_schedule(request, room_id):
    """고른 방 하나의 날짜와 시간 칸."""
    room = queries.fetch_room(room_id)
    if room is None:
        return render(
            request,
            "reservations/not_found.html",
            {"detail": "선택한 스터디룸을 찾을 수 없습니다."},
            status=404,
        )
    day, date_error = _chosen_day(request.GET.get("date", ""))
    rows = queries.fetch_reservations_for_date(day.isoformat())
    slots, past_time_count = slots_for_room(day, room, rows, request.visitor)
    today = rules.local_today()
    last = today + datetime.timedelta(days=13)
    taken = _taken_map(
        queries.fetch_reservations_between(today.isoformat(), last.isoformat())
    )
    context = {
        "room": room,
        "date_iso": day.isoformat(),
        "korean_date": rules.korean_date(day),
        "date_error": date_error,
        "is_past_day": day < today,
        "show_past_time_note": past_time_count > 0,
        "notice": NOTICES.get(request.GET.get("notice", ""), ""),
        "slots": slots,
        "days": coming_days(14, room["id"], taken, day),
    }
    return render(request, "reservations/room.html", context)


@require_visitor
@require_http_methods(["GET"])
def mine(request):
    """지금 사람의 예약만 모은 목록."""
    visitor = request.visitor
    rows = queries.fetch_my_reservations(visitor["name"], visitor["phone"])
    reservations = []
    for row in rows:
        if identity.same_person(row, visitor):
            reservations.append(present_reservation(row))
    context = {
        "reservations": reservations,
        "notice": NOTICES.get(request.GET.get("notice", ""), ""),
    }
    return render(request, "reservations/mine.html", context)


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


def _clean_name(name):
    """이름을 검사한다. 돌려주는 값은 (저장할 이름, 오류 문장)이다."""
    cleaned_name = name.strip()
    if cleaned_name == "":
        return "", MESSAGES["empty_name"]
    if len(cleaned_name) > Reservation.NAME_MAX:
        return "", MESSAGES["long_name"]
    return cleaned_name, ""


def _clean_purpose(purpose):
    """사용 목적을 검사한다. 돌려주는 값은 (저장할 목적, 오류 문장 리스트)이다."""
    cleaned_purpose = purpose.strip()
    errors = []
    if cleaned_purpose == "":
        errors.append(MESSAGES["empty_purpose"])
    elif len(cleaned_purpose) > Reservation.PURPOSE_MAX:
        errors.append(MESSAGES["long_purpose"])
    return cleaned_purpose, errors


@require_visitor
@require_http_methods(["GET", "POST"])
def reserve(request):
    """빈 칸에서 연 예약 폼. GET은 폼을 보여주고, POST는 저장을 시도한다.

    이름과 전화번호는 입장할 때 세션에 넣은 값을 쓴다.
    폼에 다른 이름을 보내도 저장하지 않는다.
    """
    room_id = _parse_room_id(_submitted(request, "room_id"))
    day, date_code = rules.parse_date(_submitted(request, "date"))
    start, start_code = rules.parse_start(_submitted(request, "start_time"))
    entered_purpose = _submitted(request, "purpose")

    # 칸 자체가 잘못된 이유를 먼저 모은다. 목적 검사보다 앞이다.
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
        cleaned_purpose, field_errors = _clean_purpose(entered_purpose)
        if len(field_errors) == 0:
            # 이름과 전화번호는 폼이 아니라 입장할 때 기억한 값이다.
            new_id = queries.insert_reservation(
                summary["room_id"],
                summary["date_iso"],
                rules.time_text(start),
                request.visitor["name"],
                request.visitor["phone"],
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
                # 저장 뒤 새로고침이 같은 저장을 다시 보내지 않도록 그 방 시간표로 보낸다.
                room_url = reverse("room", args=[summary["room_id"]])
                return redirect(
                    f"{room_url}?date={summary['date_iso']}&notice=created"
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

    taken_view = None
    if taken is not None:
        taken_view = _for_visitor(taken, request.visitor)

    context = {
        "summary": summary,
        "slot_message": slot_message,
        "taken": taken_view,
        "taken_message": MESSAGES["taken"] if taken is not None else "",
        "field_errors": field_errors,
        "save_error": save_error,
        "show_form": show_form,
        "purpose": entered_purpose,
        "back_date": back_date,
        "purpose_max": Reservation.PURPOSE_MAX,
    }
    return render(request, "reservations/reserve.html", context)


@require_visitor
@require_http_methods(["GET", "POST"])
def reservation_detail(request, reservation_id):
    """내 예약의 이름과 목적을 보여 주고, 확인 버튼이 있을 때만 취소한다.

    다른 사람의 예약은 내용을 보여 주지 않고 지우지도 않는다.
    GET으로 이 함수에 들어와도 아래 POST 분기는 실행되지 않는다.
    주소를 열거나 새로고침하는 것만으로는 예약이 지워지지 않는다.
    """
    row = queries.fetch_reservation(reservation_id)
    if row is None or not identity.same_person(row, request.visitor):
        # 없는 예약과 다른 사람 예약을 같은 문장으로 처리해 내용을 드러내지 않는다.
        detail = MESSAGES["not_mine"] if row is not None else "예약을 찾을 수 없습니다."
        return render(
            request,
            "reservations/not_found.html",
            {"detail": detail},
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
                mine_url = reverse("mine")
                return redirect(f"{mine_url}?notice=cancelled")
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
