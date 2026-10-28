from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import Engine, inspect, text
from sqlmodel import Session, SQLModel, create_engine


def make_engine(url: str) -> Engine:
    return create_engine(url, connect_args={"check_same_thread": False})


def init_db(engine: Engine) -> None:
    import backend.models  # noqa: F401  register tables

    SQLModel.metadata.create_all(engine)
    add_missing_columns(engine)


def add_missing_columns(engine: Engine) -> None:
    """create_all never alters existing tables. Add new nullable columns in place so an
    existing database keeps working after a model gains a field."""
    existing_tables = set(inspect(engine).get_table_names())
    with engine.begin() as conn:
        for table in SQLModel.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            have = {c["name"] for c in inspect(conn).get_columns(table.name)}
            for col in table.columns:
                if col.name not in have and col.nullable:
                    col_type = col.type.compile(engine.dialect)
                    conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {col_type}'))


def get_session(request: Request) -> Iterator[Session]:
    with Session(request.app.state.engine, expire_on_commit=False) as session:
        yield session
