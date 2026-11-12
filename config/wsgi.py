"""서버가 설정을 불러올 때 사용하는 입구.

python manage.py runserver 와 Vercel이 이 파일의 application 을 읽는다.
"""

import os

from django.core.wsgi import get_wsgi_application

# 설정 파일 위치를 기본값으로 넣는다.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# 서버가 요청을 받을 때 사용하는 객체.
application = get_wsgi_application()
