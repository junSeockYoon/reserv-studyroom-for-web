"""브라우저에 이름과 전화번호를 기억한다.

회원가입이나 로그인이 아니다.
같은 브라우저에서 입력한 사람을 예약 목록과 맞추기 위한 값만 세션에 둔다.
서버를 끄면 세션 표의 값이 남을 수 있지만, 나가기를 누르면 그 브라우저에서는 지운다.
"""

from . import rules

# 세션에 저장하는 키. 화면 주소에는 이름과 전화번호를 붙이지 않는다.
NAME_KEY = "visitor_name"
PHONE_KEY = "visitor_phone"


def remember(request, name, phone):
    """검사까지 끝난 이름과 숫자만 있는 전화번호를 브라우저 세션에 넣는다."""
    request.session[NAME_KEY] = name
    request.session[PHONE_KEY] = phone


def current_visitor(request):
    """지금 브라우저에 기억된 사람. 없으면 None이다."""
    name = request.session.get(NAME_KEY, "")
    phone = request.session.get(PHONE_KEY, "")
    if name == "" or phone == "":
        return None
    return {
        "name": name,
        "phone": phone,
        "phone_label": rules.format_phone(phone),
    }


def visitor_context(request):
    """모든 화면 템플릿에서 visitor 라는 이름으로 지금 사람을 읽게 한다."""
    return {"visitor": current_visitor(request)}


def same_person(row, visitor):
    """예약 줄의 이름과 전화번호가 지금 사람과 같은지 본다.

    전화번호는 둘 다 숫자만 있는 값이어야 같다.
    """
    if visitor is None:
        return False
    if row["booker_name"] != visitor["name"]:
        return False
    # 전화번호를 받기 전에 저장된 줄은 번호가 비어 있다.
    # 그 줄만 이름이 같으면 본인 예약으로 본다.
    if row["phone"] == "":
        return True
    return row["phone"] == visitor["phone"]
