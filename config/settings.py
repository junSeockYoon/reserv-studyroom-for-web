"""내 컴퓨터에서만 켜는 스터디룸 예약 연습 설정.

회원 가입, 로그인, 관리자 화면, 외부 데이터베이스는 사용하지 않는다.
서버를 켤 때 비밀번호나 계정을 입력하지 않아도 된다.
"""

from pathlib import Path

# 이 파일은 config 폴더 안에 있다.
# parent 한 번은 config, 한 번 더 올라가면 프로젝트 폴더다.
BASE_DIR = Path(__file__).resolve().parent.parent

# 폼이 다른 사이트에서 몰래 전송되지 않도록 Django가 서명할 때 쓰는 열쇠다.
# 이 프로젝트는 인터넷에 올리지 않고 내 컴퓨터에서만 실행한다.
SECRET_KEY = "txD74PhSo9OhGnVCquIdj0OLtZ8RKRPGOX8XO8J5N2ZBefWdchmfaWPi-dTZK1UJOQY"

# 오류가 나면 노란 설명 화면을 보여 준다. 연습용으로만 켠다.
DEBUG = True

# 이 서버가 응답해도 되는 주소. 내 컴퓨터의 주소만 적는다.
# testserver는 브라우저 주소가 아니라, python manage.py test 가 쓰는 이름이다.
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]

# 예약 앱만 켠다.
# django.contrib.admin 은 관리자 화면이라 넣지 않는다.
# django.contrib.auth 는 로그인 기능이라 넣지 않는다.
INSTALLED_APPS = [
    "reservations.apps.ReservationsConfig",
]

MIDDLEWARE = [
    # 기본 보안 헤더를 응답에 붙인다.
    "django.middleware.security.SecurityMiddleware",
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
            ],
        },
    },
]

# runserver가 불러오는 파일.
WSGI_APPLICATION = "config.wsgi.application"

# SQLite는 프로젝트 폴더의 db.sqlite3 파일 하나에 데이터를 저장한다.
# 사용자 이름, 비밀번호, 서버 주소가 없다.
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
