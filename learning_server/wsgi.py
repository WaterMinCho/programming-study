# -*- coding: utf-8 -*-
"""배포용 WSGI 서버가 불러오는 진입점임. 데이터 경로를 명시해야 실행됨."""
import os

from learning_server.app import Database, application as create_application

application = create_application(Database(os.environ["STUDY_DATA_DB"]))
