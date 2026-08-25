"""
공용 pytest 픽스처.

가장 중요한 역할: 모든 테스트가 임시 SQLite DB를 쓰도록 강제한다.
저장소는 프로세스 전역 싱글턴이라 격리하지 않으면 테스트가 실제 사용자의
backend/data/signal_recorder.db를 건드릴 수 있다.
"""

import pytest

from app.store.db import Database, set_database


@pytest.fixture(autouse=True)
def isolated_database(tmp_path_factory):
    """테스트마다 빈 임시 DB를 전역 저장소로 주입한다."""
    db_path = tmp_path_factory.mktemp("store") / "test.db"
    database = Database(db_path)
    database.connect()
    set_database(database)

    yield database

    database.close()
    set_database(None)
