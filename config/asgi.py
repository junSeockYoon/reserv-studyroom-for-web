"""비동기 서버용 입구.

이 연습 프로젝트에서는 사용하지 않는다.
Django가 프로젝트 뼈대를 만들 때 함께 두는 파일이라 형태만 남겨 둔다.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_asgi_application()
