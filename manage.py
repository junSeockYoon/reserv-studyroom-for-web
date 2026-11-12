#!/usr/bin/env python
"""Django 명령을 실행하는 입구.

자주 쓰는 명령:
  python manage.py migrate     표를 만들고 룸 A, 룸 B, 룸 C를 넣는다.
  python manage.py runserver   내 컴퓨터에서 웹 서버를 켠다.
  python manage.py test        예약 규칙이 지켜지는지 자동으로 확인한다.
"""

import os
import sys


def main():
    # 설정 파일이 config/settings.py라는 것을 Django에게 알려 준다.
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        # 이 함수가 migrate, runserver 같은 명령을 받아서 실행한다.
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        # 가상환경을 켜지 않았거나 Django 설치를 빼먹었을 때 여기로 온다.
        raise ImportError(
            "Django를 불러오지 못했습니다. "
            "가상환경의 파이썬으로 실행했는지, "
            "pip install -r requirements.txt 를 했는지 확인해 주세요."
        ) from exc
    # sys.argv는 터미널에 적은 명령 조각이다.
    # 예: ["manage.py", "runserver"]
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
