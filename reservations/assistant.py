"""말로 적은 예약 문장을 칸 후보로 바꾼다.

저장과 취소는 하지 않는다.
지난 시간, 운영 시간 밖, 이미 찬 칸은 rules.py와 표의 제약이 그대로 거절한다.
다른 사람의 이름, 전화번호, 목적은 이 파일로 들어오지 않는다.
"""

import datetime
import re

from . import rules
from .models import Reservation

# 요일 한 글자를 datetime의 월=0 번호로 바꾼다.
_WEEKDAYS = {"월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6}

# "두 시간"처럼 한글로 적힌 길이를 숫자로 바꾼다.
_SPAN_WORDS = {
    "한": 1,
    "하나": 1,
    "두": 2,
    "둘": 2,
    "세": 3,
    "셋": 3,
    "네": 4,
    "넷": 4,
    "다섯": 5,
}

# 시각을 직접 적지 않았을 때 찾을 시간대. 끝 시각은 포함하지 않는다.
# 저녁 (18, 21)은 18시, 19시, 20시 시작 칸이다.
_WINDOWS = {
    "아침": (9, 12),
    "오전": (9, 12),
    "점심": (12, 14),
    "오후": (12, 18),
    "저녁": (18, 21),
    "밤": (19, 21),
}

# 한 번에 제안하는 칸 묶음 수. 화면에는 이 중에서 세 개만 보여 준다.
_HORIZON_DAYS = 14
_SUGGEST_DAYS = 7
_MAX_SPAN = 4


def parse_wish(text):
    """한 문장에서 날짜, 시간, 길이, 방, 목적, 취소 여부를 꺼낸다.

    비어 있으면 empty가 True다.
    day가 None이면 날짜를 말하지 않은 것이다.
    """
    raw = "" if text is None else str(text).strip()
    parsed = {
        "empty": raw == "",
        "intent": "find",
        "day": None,
        "hour": None,
        "window": None,
        "span": 1,
        "room_letter": None,
        "purpose": "",
    }
    if raw == "":
        return parsed
    work = raw
    if _is_cancel(work):
        parsed["intent"] = "cancel"
    work, parsed["span"] = _take_span(work)
    work, hour, meridiem = _take_clock(work)
    if hour is None:
        work, parsed["window"] = _take_window(work)
    else:
        parsed["hour"] = _clock_hour(hour, meridiem)
    work, parsed["day"] = _take_day(work, rules.local_today())
    work, parsed["room_letter"] = _take_room(work)
    parsed["purpose"] = _purpose(work)
    return parsed


def find_options(parsed, rooms, occupied, own_slots, limit=3):
    """조건에 맞는 빈 칸 묶음을 최대 limit개 고른다.

    occupied는 (방 번호, 날짜 글자, 시작 시각 글자) 집합이다.
    이름이나 목적은 들어 있지 않다.
    own_slots는 이 사람 예약의 방과 시각만 담는다. 자주 쓴 방을 앞에 둔다.
    """
    today = rules.local_today()
    if parsed["day"] is not None:
        days = [parsed["day"]]
    else:
        days = []
        offset = 0
        while offset < _HORIZON_DAYS:
            days.append(today + datetime.timedelta(days=offset))
            offset = offset + 1

    chosen_rooms = _rooms_for_letter(rooms, parsed["room_letter"])
    usual_room = _most_common(own_slots, "room_id")
    ranked = []
    for day in days:
        day_offset = (day - today).days
        if day_offset < 0:
            # 이미 지난 날짜는 후보에 넣지 않는다.
            continue
        for room in chosen_rooms:
            for start in rules.allowed_starts():
                if not _hour_matches(start.hour, parsed):
                    continue
                block = _open_block(room["id"], day, start, parsed["span"], occupied)
                if block is None:
                    continue
                if usual_room is not None and room["id"] == usual_room:
                    room_rank = 0
                else:
                    room_rank = 1
                ranked.append((day_offset, room_rank, start.hour, room["id"], room, day, block))

    ranked.sort()
    options = []
    for item in ranked[:limit]:
        room = item[4]
        day = item[5]
        block = item[6]
        first = block[0]
        last = block[-1]
        options.append(
            {
                "room_id": room["id"],
                "room_name": room["name"],
                "date_iso": day.isoformat(),
                "korean_date": rules.korean_date(day),
                "start_hm": f"{first.hour:02d}:{first.minute:02d}",
                "span": len(block),
                "range_label": f"{first.hour:02d}:00~{last.hour + 1:02d}:00",
                "purpose": parsed["purpose"],
            }
        )
    return options


def match_cancellations(parsed, own_slots):
    """이 사람 예약 중에서 문장에 맞는 것만 고른다.

    날짜를 말하지 않으면 오늘 이후만 본다.
    여기서 줄을 지우지는 않는다.
    """
    today = rules.local_today()
    matches = []
    for row in own_slots:
        day = datetime.date.fromisoformat(row["date"])
        if parsed["day"] is not None and day != parsed["day"]:
            continue
        if parsed["day"] is None and day < today:
            continue
        letter = parsed["room_letter"]
        if letter is not None and not row["room_name"].upper().endswith(letter.upper()):
            continue
        start = datetime.time.fromisoformat(row["start_time"])
        if not _hour_matches(start.hour, parsed):
            continue
        matches.append(row)
    return matches


def suggest_slot(rooms, occupied, own_slots):
    """첫 화면에 띄울 칸 하나.

    이 사람이 자주 잡은 시각과 방을 먼저 보고, 그 칸이 차 있으면 가까운 빈 칸을 고른다.
    예약이 하나도 없으면 가장 빠른 빈 칸을 고른다.
    없는 경우에는 None이다.
    """
    today = rules.local_today()
    usual_hour = _most_common_hour(own_slots)
    usual_room = _most_common(own_slots, "room_id")
    best = None
    best_key = None
    offset = 0
    while offset < _SUGGEST_DAYS:
        day = today + datetime.timedelta(days=offset)
        for room in rooms:
            for start in rules.allowed_starts():
                if rules.calendar_block(day, start) is not None:
                    continue
                key_slot = (room["id"], day.isoformat(), rules.time_text(start))
                if key_slot in occupied:
                    continue
                if usual_hour is None or start.hour == usual_hour:
                    hour_rank = 0
                else:
                    hour_rank = 1
                if usual_room is None or room["id"] == usual_room:
                    room_rank = 0
                else:
                    room_rank = 1
                if usual_hour is None:
                    hour_gap = 0
                else:
                    hour_gap = abs(start.hour - usual_hour)
                key = (hour_rank, room_rank, offset, hour_gap, start.hour, room["id"])
                if best_key is None or key < best_key:
                    best_key = key
                    best = (room, day, start)
        offset = offset + 1
    if best is None:
        return None
    room, day, start = best
    return {
        "sentence": f"{_when(today, day)} {start.hour}시 {room['name']}를 쓸 수 있어요.",
        "room_id": room["id"],
        "date_iso": day.isoformat(),
        "start_hm": f"{start.hour:02d}:{start.minute:02d}",
    }


def _is_cancel(text):
    """취소해 달라는 말인지 본다."""
    for word in ("취소", "지워", "삭제"):
        if word in text:
            return True
    return False


def _take_span(text):
    """'두 시간' 같은 길이를 숫자로 바꾸고 그 말은 문장에서 뺀다."""
    found = re.search(r"(한|하나|두|둘|세|셋|네|넷|다섯|\d+)\s*시간", text)
    if found is None:
        return text, 1
    word = found.group(1)
    if word.isdigit():
        span = int(word)
    else:
        span = _SPAN_WORDS[word]
    if span < 1:
        span = 1
    if span > _MAX_SPAN:
        span = _MAX_SPAN
    return _cut(text, found.start(), found.end()), span


def _take_clock(text):
    """'오후 3시'나 '18:00'을 찾아 시 숫자와 오전/오후 말을 돌려준다."""
    clock = re.search(r"(\d{1,2})\s*:\s*(\d{2})", text)
    named = re.search(r"(오전|오후|아침|저녁|밤|점심)?\s*(\d{1,2})\s*시", text)
    if clock is not None and (named is None or clock.start() <= named.start()):
        hour = int(clock.group(1))
        return _cut(text, clock.start(), clock.end()), hour, None
    if named is None:
        return text, None, None
    hour = int(named.group(2))
    meridiem = named.group(1)
    return _cut(text, named.start(), named.end()), hour, meridiem


def _clock_hour(hour, meridiem):
    """오전/오후와 '3시'를 운영 시간에 맞게 24시 기준으로 바꾼다.

    오전·오후가 없고 1시부터 8시면 오후로 본다. 새벽에 여는 칸이 없기 때문이다.
    9시부터 20시는 적은 숫자를 그대로 쓴다.
    """
    if hour < 0 or hour > 23:
        return None
    if meridiem == "오후" and hour < 12:
        return hour + 12
    if meridiem in ("저녁", "밤") and hour <= 11:
        return hour + 12
    if meridiem == "오전" and hour == 12:
        return 0
    if meridiem is None and 1 <= hour <= 8:
        return hour + 12
    return hour


def _take_window(text):
    """저녁, 오후처럼 시간대 단어를 찾는다. 먼저 나오는 단어를 쓴다."""
    found_at = None
    found_name = None
    for name in _WINDOWS:
        at = text.find(name)
        if at == -1:
            continue
        if found_at is None or at < found_at:
            found_at = at
            found_name = name
    if found_name is None:
        return text, None
    end = found_at + len(found_name)
    return _cut(text, found_at, end), _WINDOWS[found_name]


def _take_day(text, today):
    """오늘, 내일, 요일, '11월 13일' 중 날짜를 하나 정하고 그 말을 뺀다."""
    day = None
    if "모레" in text:
        day = today + datetime.timedelta(days=2)
        text = text.replace("모레", " ", 1)
    elif "내일" in text:
        day = today + datetime.timedelta(days=1)
        text = text.replace("내일", " ", 1)
    elif "오늘" in text:
        day = today + datetime.timedelta(days=0)
        text = text.replace("오늘", " ", 1)

    weekday = re.search(
        r"(다음\s*주|이번\s*주)?\s*(월|화|수|목|금|토|일)요일",
        text,
    )
    if weekday is not None:
        if day is None:
            which = weekday.group(1) or ""
            which = which.replace(" ", "")
            day = _weekday_date(today, _WEEKDAYS[weekday.group(2)], which)
        text = _cut(text, weekday.start(), weekday.end())

    month_day = re.search(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일", text)
    if month_day is not None:
        if day is None:
            month = int(month_day.group(1))
            date_num = int(month_day.group(2))
            try:
                picked = datetime.date(today.year, month, date_num)
            except ValueError:
                picked = None
            if picked is not None and picked < today:
                try:
                    picked = datetime.date(today.year + 1, month, date_num)
                except ValueError:
                    picked = None
            day = picked
        text = _cut(text, month_day.start(), month_day.end())
    return text, day


def _weekday_date(today, weekday, which):
    """이번 주 또는 다음 주의 그 요일 날짜."""
    if which == "이번주":
        monday = today - datetime.timedelta(days=today.weekday())
        return monday + datetime.timedelta(days=weekday)
    ahead = (weekday - today.weekday()) % 7
    if which == "다음주":
        if ahead == 0:
            ahead = 7
        else:
            ahead = ahead + 7
    return today + datetime.timedelta(days=ahead)


def _take_room(text):
    """'룸 A', 'A룸', '방 B'에서 방 글자를 찾는다."""
    found = re.search(r"룸\s*([A-Ca-c])|방\s*([A-Ca-c])|([A-Ca-c])\s*룸", text)
    if found is None:
        return text, None
    letter = found.group(1) or found.group(2) or found.group(3)
    return _cut(text, found.start(), found.end()), letter.upper()


def _purpose(text):
    """시간과 방을 뺀 뒤에 남은 말을 사용 목적으로 본다."""
    cleaned = text
    for phrase in (
        "취소해 주세요",
        "취소해줘",
        "취소 해줘",
        "취소해 줘",
        "지워 주세요",
        "지워줘",
        "지워 줘",
        "삭제해 줘",
        "해 주세요",
        "해주세요",
        "해 줘",
        "해줘",
        "찾아 줘",
        "찾아줘",
        "잡아 줘",
        "잡아줘",
        "취소",
        "지워",
        "삭제",
    ):
        cleaned = cleaned.replace(phrase, " ")
    cleaned = cleaned.replace(",", " ").replace(".", " ")
    words = []
    skip = {
        "에",
        "에서",
        "으로",
        "로",
        "은",
        "는",
        "이",
        "가",
        "을",
        "를",
        "도",
        "만",
        "부터",
        "까지",
        "동안",
        "하고",
        "와",
        "과",
        "좀",
        "거",
        "것",
        "자리",
        "예약",
        "싶어",
        "싶은",
        "부탁",
    }
    for word in cleaned.split():
        if word in skip:
            continue
        words.append(word)
    purpose = " ".join(words).strip()
    if len(purpose) > Reservation.PURPOSE_MAX:
        purpose = purpose[: Reservation.PURPOSE_MAX]
    return purpose


def _hour_matches(hour, parsed):
    """이 시작 시가 문장의 시각 또는 시간대 안에 있는지 본다."""
    if parsed["hour"] is not None:
        return hour == parsed["hour"]
    window = parsed["window"]
    if window is None:
        return True
    return window[0] <= hour < window[1]


def _rooms_for_letter(rooms, letter):
    """방 글자가 있으면 그 방만, 없으면 모든 방을 돌려준다."""
    if letter is None:
        return list(rooms)
    chosen = []
    for room in rooms:
        if str(room["name"]).upper().endswith(letter.upper()):
            chosen.append(room)
    return chosen


def _open_block(room_id, day, start, span, occupied):
    """시작 시각부터 span칸이 모두 운영 시간 안이고 비어 있으면 그 시각 목록을 돌려준다."""
    block = []
    hour = start.hour
    while len(block) < span:
        candidate = datetime.time(hour, 0)
        if not rules.is_allowed_start(candidate):
            return None
        if rules.calendar_block(day, candidate) is not None:
            return None
        slot_key = (room_id, day.isoformat(), rules.time_text(candidate))
        if slot_key in occupied:
            return None
        block.append(candidate)
        hour = hour + 1
    return block


def _most_common(rows, key):
    """같은 값이 가장 많은 항목. 수가 같으면 나중 예약을 따른다."""
    if len(rows) == 0:
        return None
    counts = {}
    chosen = None
    for row in rows:
        value = row[key]
        counts[value] = counts.get(value, 0) + 1
        if chosen is None or counts[value] >= counts[chosen]:
            chosen = value
    return chosen


def _most_common_hour(rows):
    """자주 잡은 시작 시."""
    with_hour = []
    for row in rows:
        start = datetime.time.fromisoformat(row["start_time"])
        with_hour.append({"hour": start.hour})
    return _most_common(with_hour, "hour")


def _when(today, day):
    """오늘, 내일, 모레 또는 '11월 14일'."""
    gap = (day - today).days
    if gap == 0:
        return "오늘"
    if gap == 1:
        return "내일"
    if gap == 2:
        return "모레"
    return f"{day.month}월 {day.day}일"


def _cut(text, start, end):
    """찾은 구간을 공백으로 바꿔 앞뒤 단어가 붙지 않게 한다."""
    return text[:start] + " " + text[end:]
