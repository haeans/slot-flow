from logging.config import fileConfig

from sqlalchemy import create_engine, event, pool

from alembic import context

from app.storage import db

# DB 구조는 이 절차들로만 만들고 바꾼다. (D-064)
# DB 경로는 alembic.ini 가 아니라 app.storage.db 를 따른다. 테스트의 set_db_path 도 그대로 적용된다.
config = context.config

# 서버가 시작할 때 부르는 경우(init_db)에는 로그 설정을 건드리지 않는다. uvicorn 로그가 꺼지기 때문이다.
if config.config_file_name is not None and not config.attributes.get("skip_logging"):
    fileConfig(config.config_file_name)

# SQLAlchemy 모델을 쓰지 않는다. 절차는 SQL로 직접 쓴다. (STRICT·트리거를 그대로 두기 위해)
target_metadata = None


def db_url() -> str:
    return f"sqlite:///{db.get_db_path().as_posix()}"


def run_migrations_offline() -> None:
    context.configure(url=db_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(db_url(), poolclass=pool.NullPool)

    @event.listens_for(engine, "connect")
    def _foreign_keys_on(dbapi_conn, _record):
        # SQLite는 외래키 검사를 연결마다 켜야 한다. (D-032)
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
