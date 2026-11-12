"""내 컴퓨터에서 켜는 스터디룸 예약 설정.

데이터베이스 주소가 없으면 SQLite 파일을 쓴다. 비밀번호가 필요 없다.
프로젝트 폴더의 .env에 Supabase 주소가 있으면 그 PostgreSQL에 연결한다.
회원 가입, 로그인, 관리자 화면은 만들지 않는다.
"""

import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

# 이 파일은 config 폴더 안에 있다.
# parent 한 번은 config, 한 번 더 올라가면 프로젝트 폴더다.
BASE_DIR = Path(__file__).resolve().parent.parent


def load_env_file(path):
    """프로젝트 폴더의 .env를 읽어 환경 변수로 넣는다.

    이미 터미널에서 같은 이름이 정해져 있으면 파일 값으로 덮지 않는다.
    비밀번호를 settings.py에 직접 적지 않기 위한 파일이다.
    """
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        # 빈 줄과 #으로 시작하는 설명은 건너뛴다.
        if line == "" or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        # 값 양쪽에 따옴표를 붙여 둔 경우 떼어 낸다.
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key != "" and key not in os.environ:
            os.environ[key] = value


def database_from_url(url):
    """postgresql://사용자:비밀번호@호스트:포트/데이터베이스 를 Django 설정으로 바꾼다."""
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").split("+", 1)[0]
    if scheme not in ("postgres", "postgresql"):
        raise ValueError(
            "DATABASE_URL은 postgresql:// 로 시작해야 합니다. "
            "Supabase의 URI를 그대로 붙여 주세요."
        )
    # 주소 뒤의 ?sslmode=require 같은 옵션을 읽는다.
    query = parse_qs(parsed.query)
    if "sslmode" in query and query["sslmode"]:
        sslmode = query["sslmode"][0]
    else:
        # Supabase는 암호화되지 않은 접속을 거절하므로 기본값은 require다.
        sslmode = "require"
    database_name = unquote(parsed.path.lstrip("/")) or "postgres"
    port = parsed.port or 5432
    options = {"sslmode": sslmode}
    config = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": database_name,
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": str(port),
        "OPTIONS": options,
        # 요청마다 연결을 새로 연다. 연습용 서버에는 이 설정이 단순하다.
        "CONN_MAX_AGE": 0,
    }
    # 6543은 Supabase 트랜잭션 풀러다. Django의 서버 쪽 커서를 끄면 조회는 된다.
    # 표 생성(migrate)은 세션 모드(5432) 주소로 하는 편이 안전하다.
    if port == 6543:
        config["DISABLE_SERVER_SIDE_CURSORS"] = True
    return config


# .env가 있으면 그 안의 DATABASE_URL을 지금 읽어 둔다.
load_env_file(BASE_DIR / ".env")

# 폼이 다른 사이트에서 몰래 전송되지 않도록 Django가 서명할 때 쓰는 열쇠다.
# 이 프로젝트는 인터넷에 올리지 않고 내 컴퓨터에서만 실행한다.
SECRET_KEY = "txD74PhSo9OhGnVCquIdj0OLtZ8RKRPGOX8XO8J5N2ZBefWdchmfaWPi-dTZK1UJOQY"

# 오류가 나면 노란 설명 화면을 보여 준다. 연습용으로만 켠다.
DEBUG = True

# 이 서버가 응답해도 되는 주소. 내 컴퓨터의 주소만 적는다.
# testserver는 브라우저 주소가 아니라, python manage.py test 가 쓰는 이름이다.
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]

# 예약 앱과, 브라우저에 이름·전화번호를 기억할 세션만 켠다.
# django.contrib.admin 은 관리자 화면이라 넣지 않는다.
# django.contrib.auth 는 회원 로그인이라 넣지 않는다.
# 세션은 회원 가입이 아니라, 이 브라우저에서 입력한 사람을 예약 목록과 맞추는 용도다.
INSTALLED_APPS = [
    "django.contrib.sessions",
    "reservations.apps.ReservationsConfig",
]

MIDDLEWARE = [
    # 기본 보안 헤더를 응답에 붙인다.
    "django.middleware.security.SecurityMiddleware",
    # 세션 쿠키를 읽고, 이름과 전화번호를 요청 동안 꺼내 준다.
    "django.contrib.sessions.middleware.SessionMiddleware",
    # 주소 끝의 슬래시(/)를 맞추고, 너무 긴 주소를 거절한다.
    "django.middleware.common.CommonMiddleware",
    # 저장·취소 폼이 우리 화면에서 왔는지 확인한다.
    "django.middleware.csrf.CsrfViewMiddleware",
    # 다른 사이트가 이 화면을 프레임 안에 넣지 못하게 한다.
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# 주소 목록이 있는 파일.
ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # HTML 파일은 각 앱의 templates 폴더에서 찾는다.
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                # {% csrf_token %}이 숨은 입력값을 만들 때 필요하다.
                "django.template.context_processors.csrf",
                # 템플릿에서 요청 주소 같은 정보를 읽을 수 있게 한다.
                "django.template.context_processors.request",
                # 모든 화면에서 지금 입력한 사람의 이름과 전화번호를 읽는다.
                "reservations.identity.visitor_context",
            ],
        },
    },
]

# runserver가 불러오는 파일.
WSGI_APPLICATION = "config.wsgi.application"

# 테스트는 항상 이 컴퓨터의 SQLite를 쓴다.
# Supabase에 테스트용 데이터베이스를 만들 권한이 없고,
# 자동 테스트가 실제 예약 데이터를 지우면 안 되기 때문이다.
RUNNING_TESTS = "test" in sys.argv
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

if DATABASE_URL and not RUNNING_TESTS:
    # Supabase PostgreSQL. 예약 조회와 저장이 이 서버로 간다.
    DATABASES = {"default": database_from_url(DATABASE_URL)}
else:
    # 주소가 없으면 db.sqlite3 파일 하나에 저장한다. 비밀번호가 없다.
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# 화면 문장은 우리가 한국어로 직접 적지만, Django 기본 언어도 한국어로 맞춘다.
LANGUAGE_CODE = "ko-kr"

# 지난 시간인지 판단할 때 이 시간대를 쓴다. 한국 표준시다.
TIME_ZONE = "Asia/Seoul"

USE_I18N = True

# 데이터베이스에는 UTC로 저장하고, 비교할 때는 위 TIME_ZONE으로 바꾼다.
USE_TZ = True

# 새 표의 번호 칸은 큰 정수로 만든다.
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
