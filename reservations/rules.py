"""예약할 수 있는 날짜와 시간을 판단하는 규칙.

운영 시간은 09:00부터 21:00까지다.
예약은 1시간 단위이고, 마지막 시작 시각은 20:00이다.
지난 날짜와, 오늘 이미 시작한 시간과, 운영 시간 밖은 예약할 수 없다.
"""

import datetime

from django.utils import timezone
from django.utils.dateparse import parse_datetime

# 문을 여는 시. 첫 칸은 09:00~10:00이다.
OPEN_HOUR = 9
# 문을 닫는 시. 21:00에 시작하는 칸은 없다.
CLOSE_HOUR = 21


def allowed_starts():
    """예약 시작으로 허용하는 시각 목록.

    range(9, 21)은 9 이상 21 미만이라 9, 10, ..., 20이다.
    각 시각은 정각이고, 한 칸은 그 시각부터 한 시간이다.
    """
    starts = []
    hour = OPEN_HOUR
    while hour < CLOSE_HOUR:
        starts.append(datetime.time(hour, 0))
        hour = hour + 1
    return starts


def is_allowed_start(start):
    """시작 시각이 운영 시간 안의 정각인지 확인한다."""
    # 목록을 매번 만들어 비교한다. 칸이 12개뿐이라 충분하다.
    return start in allowed_starts()


def slot_label(start):
    """09:00~10:00처럼 한 칸의 시작과 끝을 글자로 만든다."""
    end_hour = start.hour + 1
    return f"{start.hour:02d}:{start.minute:02d}~{end_hour:02d}:00"


def time_text(start):
    """데이터베이스에 넣는 시작 시각.

    항상 시:분:초 두 자리로 맞춘다. 예: 09:00:00
    고유 제약은 글자가 완전히 같을 때만 같은 값으로 본다.
    어떤 예약은 9:00:00, 어떤 예약은 09:00:00으로 쓰면 제약이 놓칠 수 있다.
    """
    return f"{start.hour:02d}:{start.minute:02d}:00"


def local_now():
    """지금 시각을 한국 시간으로 돌려준다.

    settings.py의 TIME_ZONE이 Asia/Seoul이다.
    """
    return timezone.localtime(timezone.now())


def local_today():
    """한국 달력 기준 오늘 날짜."""
    return local_now().date()


def korean_date(day):
    """2026년 11월 12일 (목)처럼 화면에 보여줄 날짜."""
    weekdays = ["월", "화", "수", "목", "금", "토", "일"]
    weekday = weekdays[day.weekday()]
    return f"{day.year}년 {day.month}월 {day.day}일 ({weekday})"


def parse_date(text):
    """주소나 폼의 날짜 글자를 날짜로 바꾼다.

    성공하면 (날짜, None), 실패하면 (None, "bad_date")를 돌려준다.
    """
    if text is None:
        return None, "bad_date"
    raw = str(text).strip()
    if raw == "":
        return None, "bad_date"
    try:
        # 2026-11-13 형식만 받는다. 다른 형식이면 ValueError가 난다.
        return datetime.date.fromisoformat(raw), None
    except ValueError:
        return None, "bad_date"


def parse_start(text):
    """시작 시각 글자를 시각으로 바꾼다.

    09:00과 09:00:00은 받는다.
    운영 시간 밖이거나 정각이 아니면 outside_hours다.
    시각으로 읽을 수 없으면 bad_time이다.
    """
    if text is None:
        return None, "bad_time"
    raw = str(text).strip()
    parts = raw.split(":")
    # 시:분 또는 시:분:초만 허용한다.
    if len(parts) not in (2, 3):
        return None, "bad_time"
    try:
        hour = int(parts[0])
        minute = int(parts[1])
        if len(parts) == 3:
            second = int(parts[2])
        else:
            second = 0
    except ValueError:
        return None, "bad_time"
    if hour < 0 or hour > 23 or minute < 0 or minute > 59 or second < 0 or second > 59:
        return None, "bad_time"
    start = datetime.time(hour, minute, second)
    # 09:30이나 21:00처럼 칸 목록에 없으면 운영 시간 밖이다.
    if not is_allowed_start(start):
        return None, "outside_hours"
    return start, None


def calendar_block(day, start):
    """이미 시각이 허용된 칸이 오늘 기준으로 지났는지 확인한다.

    예약할 수 있으면 None을 돌려준다.
    지난 날짜면 past_date, 오늘 이미 시작한 칸이면 past_time이다.
    """
    today = local_today()
    if day < today:
        return "past_date"
    if day > today:
        # 내일 이후는 운영 시간 안이면 전부 예약할 수 있다.
        return None
    now = local_now()
    # 오늘 날짜와 시작 시각을 하나의 시각으로 합친다.
    start_at = datetime.datetime.combine(day, start, tzinfo=now.tzinfo)
    # 시작 시각이 지금과 같거나 이전이면 그 칸은 이미 시작했다.
    if start_at <= now:
        return "past_time"
    return None


def stored_datetime_as_seoul(value):
    """SQLite에 넣은 UTC 시각 글자를 한국 시각 글자로 바꾼다.

    예약 가능 여부를 판단하는 데는 쓰지 않는다.
    """
    if value is None or value == "":
        return ""
    parsed = parse_datetime(str(value))
    if parsed is None:
        return str(value)
    if timezone.is_naive(parsed):
        # 시간 표시가 없는 값은 UTC 벽시계로 저장해 두었다.
        parsed = timezone.make_aware(parsed, datetime.timezone.utc)
    local = timezone.localtime(parsed)
    return (
        f"{local.year}년 {local.month}월 {local.day}일 "
        f"{local.hour:02d}:{local.minute:02d}"
    )
