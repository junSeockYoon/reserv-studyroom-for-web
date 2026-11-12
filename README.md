# 스터디룸 예약

방 세 개의 시간표를 보고, 빈 칸을 예약하거나 예약을 취소하는 연습용 웹 앱입니다. 이 폴더는 게시판 프로젝트와 따로 있습니다. 회원가입, 로그인, 관리자 화면, 배포 설정은 만들지 않았습니다. 들어갈 때 이름과 전화번호를 입력하고, 예약 목록에는 그 사람의 예약만 나옵니다.

- 파이썬 3.14
- Django 6.1.3
- 데이터베이스는 둘 중 하나입니다. `.env`에 Supabase 주소가 있으면 그 PostgreSQL을 쓰고, 없으면 `db.sqlite3` 파일을 씁니다.

## 실행 방법

PowerShell을 열고 이 폴더로 이동합니다.

```powershell
cd C:\Project\reserve-studyroom
```

처음 한 번만, 가상환경을 만들고 Django를 설치합니다. 이미 `.venv` 폴더가 있으면 이 두 줄은 건너뜁니다.

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

표를 만들고 룸 A, 룸 B, 룸 C를 넣습니다. 데이터베이스 파일이 없을 때 한 번 실행하면 됩니다.

```powershell
.\.venv\Scripts\python.exe manage.py migrate
```

서버를 켭니다.

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

브라우저에서 http://127.0.0.1:8000/ 을 엽니다. 서버를 끌 때는 그 터미널에서 `Ctrl+C`를 누릅니다.

가상환경을 켜고 싶다면 아래를 먼저 실행한 뒤 `python manage.py runserver`라고 쳐도 됩니다. 실행 정책 때문에 `Activate.ps1`이 막히면, 위의 `.\.venv\Scripts\python.exe` 방식을 쓰면 됩니다.

```powershell
.\.venv\Scripts\Activate.ps1
```

규칙을 자동으로 확인하고 싶을 때는 서버를 켜지 않고 다음을 실행합니다.

```powershell
.\.venv\Scripts\python.exe manage.py test
```

데이터를 처음부터 다시 만들고 싶으면 서버를 끈 뒤 `db.sqlite3` 파일을 삭제하고 `migrate`를 다시 실행합니다. 방 세 개는 마이그레이션이 다시 넣습니다. Supabase를 쓰는 경우에는 파일을 지우지 말고, Supabase 표 편집기에서 데이터를 지우거나 프로젝트에서 표를 다시 만들면 됩니다.

## Supabase 연결

예약 목록은 `queries.py`의 SQL이 읽습니다. 데이터베이스만 Supabase로 바꾸면 같은 화면이 그 서버의 데이터를 보여주고 저장합니다.

1. [Supabase](https://supabase.com)에서 프로젝트를 만듭니다. 지역은 한국과 가까운 Northeast Asia(서울)를 고르면 됩니다.
2. 프로젝트 비밀번호를 적어 둡니다. 이 비밀번호가 데이터베이스 비밀번호입니다.
3. 프로젝트 화면의 **Connect**를 누릅니다.
4. **Connection string**에서 **URI**를 고르고, 방식은 **Session**을 고릅니다. 주소의 포트는 `5432`입니다. `6543` 트랜잭션 풀러는 표 생성과 맞지 않아서 쓰지 않습니다.
5. 이 프로젝트 폴더의 `.env.example`을 복사해 `.env` 파일을 만듭니다.

```powershell
Copy-Item .env.example .env
```

6. `.env`의 `DATABASE_URL=` 오른쪽에 복사한 주소를 붙입니다. 별표로 나온 비밀번호 자리는 2번에서 적어 둔 비밀번호로 바꿉니다. 비밀번호에 `@`, `#`, `%`가 있으면 Supabase가 보여 주는 인코딩된 주소를 그대로 붙입니다.
7. PostgreSQL 연결 패키지를 설치하고, Supabase에 표와 방 세 개를 만듭니다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

`migrate`가 끝나면 Supabase의 **Table Editor**에 `study_room`과 `reservation` 표가 보입니다. `study_room`에는 룸 A, 룸 B, 룸 C가 들어 있습니다. 화면에서 만든 예약은 `reservation` 표에 쌓입니다. 예약 줄에는 이름, 전화번호, 사용 목적이 함께 저장됩니다.

예전에 SQL로 `reservation` 표를 직접 만들어 두었고 그 표에 `phone` 칸이 없다면, Supabase SQL Editor에서 아래를 한 번 실행합니다. Django `migrate`로 표를 만든 경우에는 0003 마이그레이션이 이 칸을 넣으므로 아래 SQL은 다시 실행하지 않아도 됩니다.

```sql
ALTER TABLE "reservation"
ADD COLUMN IF NOT EXISTS "phone" varchar(20) NOT NULL DEFAULT '';
```

`.env`를 지우거나 `DATABASE_URL`을 비우면 다시 이 컴퓨터의 `db.sqlite3`를 사용합니다. `python manage.py test`는 실제 Supabase 데이터를 건드리지 않도록 항상 SQLite로 실행됩니다.

## 폴더 역할

```
reserve-studyroom/
├── manage.py                 서버를 켜고 명령을 실행하는 입구
├── requirements.txt          설치할 Django와 PostgreSQL 연결 패키지
├── README.md                 이 설명서
├── .env.example              Supabase 주소 예시. 복사해서 .env 로 쓴다
├── .env                      실제 Supabase 주소. 비밀번호가 들어 있어 GitHub에 올리지 않는다
├── db.sqlite3                DATABASE_URL이 없을 때 생기는 데이터베이스 파일
├── .venv/                    이 프로젝트만의 파이썬 가상환경
├── config/
│   ├── settings.py           한국어, 한국 시간, SQLite 또는 Supabase 설정
│   ├── urls.py               주소의 시작점
│   ├── wsgi.py               로컬 서버가 설정을 불러오는 입구
│   └── asgi.py               이 연습에서는 사용하지 않는 입구
└── reservations/
    ├── models.py             방 표, 예약 표, 중복 금지 제약
    ├── rules.py              운영 시간과 지난 날짜 판단
    ├── queries.py            예약 조회, 저장, 삭제 SQL
    ├── views.py              시간표, 예약 폼, 취소 화면
    ├── urls.py               기능별 주소
    ├── tests.py              규칙 자동 확인
    ├── migrations/           표를 만들고 방 세 개를 넣는 기록
    └── templates/reservations/
        ├── base.html         공통 화면과 <style> 안의 CSS
        ├── schedule.html     방을 고르는 첫 화면
        ├── room.html         고른 방의 날짜와 시간
        ├── mine.html         내 예약 목록
        ├── enter.html        들어갈 때 이름과 전화번호를 받는 화면
        ├── reserve.html      사용 목적을 입력하는 폼
        ├── detail.html       예약 내용과 취소 확인
        └── not_found.html    없는 주소
```

화면 디자인은 `base.html`의 `<style>` 안에 있습니다. 별도의 CSS 파일이나 프론트엔드 프레임워크는 쓰지 않습니다.

## 화면에서 하는 일

1. 처음 열면 이름과 전화번호를 입력해야 시간표가 나옵니다. 회원 가입은 없고, 이 브라우저에만 기억합니다. 010-1234-5678과 01012345678은 같은 번호로 봅니다.
2. 첫 화면에서 룸 A, 룸 B, 룸 C 중 방을 고릅니다. 방마다 앞으로 7일의 남은 칸이 보입니다.
3. 고른 방의 날짜를 누르면 그 방의 시간 칸만 나옵니다. 연한 초록 칸을 누르면 사용 목적만 입력합니다. 이름과 전화번호는 입장할 때 입력한 값이 저장됩니다.
4. 내가 예약한 파란 칸은 "내 예약"으로 보이고, 누르면 내용이 나옵니다. **예약 취소** 버튼을 눌러야 삭제됩니다. 주소만 열거나 새로고침하면 취소되지 않습니다.
5. 다른 사람의 파란 칸은 "예약됨"만 보입니다. 이름, 전화번호, 목적은 나오지 않고, 그 예약 주소로 들어가거나 취소할 수도 없습니다.
6. 회색 칸은 지난 날짜이거나 오늘 이미 시작한 시간입니다.
7. 운영 시간은 09:00~21:00이고, 예약은 1시간입니다. 마지막 시작 시간은 20:00입니다.
8. 위쪽 예약 내역에는 지금 사람의 예약만 나옵니다. 없으면 "아직 내가 예약한 내용이 없습니다"라고 보여 줍니다.
9. 이름이나 전화번호가 비었거나, 지난 시간이나 운영 시간 밖을 저장하려고 하면 이유를 보여 주고 저장하지 않습니다.
10. 같은 칸을 다시 예약하면 저장하지 않고, 이미 예약된 이유를 보여 줍니다. 그 칸이 다른 사람 것이면 상대 정보는 보여 주지 않습니다.

## 예약이 겹치지 않게 막는 방법

겹침 방지는 두 겹입니다.

### 1. 저장 전에 SQL로 같은 칸을 찾는다

`reservations/queries.py`의 `fetch_reservation_for_slot`이 아래처럼 조회합니다. 한 줄이라도 있으면 `views.py`는 INSERT 하지 않고 "이미 예약되어 있습니다"를 보여 줍니다.

```sql
SELECT ...
FROM "reservation"
JOIN "study_room" ON "study_room"."id" = "reservation"."room_id"
WHERE "reservation"."room_id" = %s
  AND "reservation"."date" = %s
  AND "reservation"."start_time" = %s
```

`%s`는 자리 표시자입니다. 방 번호, 날짜, 시작 시각은 SQL 문장에 이어 붙이지 않고 `cursor.execute(sql, [방 번호, 날짜, 시각])`의 리스트로 넘깁니다. Django가 SQLite에 넘기기 전에 `%s`를 `?`로 바꿉니다. 이름에 따옴표나 `%`가 들어 있어도 예약 내용 글자로만 저장됩니다.

### 2. 데이터베이스 제약으로 두 번째 줄을 거부한다

위 확인과 INSERT 사이에 같은 칸 저장이 한 번 더 들어올 수 있습니다. 그래서 표를 만들 때 제약을 같이 만듭니다. `python manage.py sqlmigrate reservations 0001`의 예약 표 정의에는 다음이 들어 있습니다.

```sql
CONSTRAINT "one_reservation_per_slot" UNIQUE ("room_id", "date", "start_time")
```

같은 `room_id`, `date`, `start_time`은 한 줄만 허용됩니다. 두 번째 INSERT는 SQLite가 거부하고, 코드는 그 오류를 잡아서 같은 안내 문장을 보여 줍니다. 화면 확인을 건너뛰고 INSERT만 두 번 해도 줄은 하나로 남습니다.

글자 수 제한은 이 제약과 다릅니다. SQLite는 `varchar(30)` 길이를 스스로 검사하지 않아서, 이름 30자, 전화번호 형식, 목적 100자는 `views.py`가 저장 전에 검사합니다. 다른 사람의 예약은 목록에서 빼기 전에 SQL로 읽지만, 화면으로 보내기 전에 이름과 전화번호와 목적을 제거합니다.

## 데이터를 직접 보고 싶을 때

서버를 켠 상태에서도 `db.sqlite3`를 SQLite 프로그램으로 열 수 있습니다. 표 이름은 `study_room`과 `reservation`입니다. 시작 시각은 `09:00:00`처럼 초까지 붙인 글자로 저장됩니다. 형식을 일정하게 맞춰야 고유 제약이 같은 칸을 같은 값으로 알아봅니다.
