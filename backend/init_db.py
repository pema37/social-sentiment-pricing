from sqlmodel import SQLModel

from db.session import sync_engine
from models.user import User  # noqa: F401


def init_db() -> None:
    SQLModel.metadata.create_all(bind=sync_engine)


if __name__ == "__main__":
    init_db()
