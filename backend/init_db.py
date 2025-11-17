from sqlmodel import SQLModel

from backend.db.session import engine
from backend.models.user import User  # noqa: F401


def init_db() -> None:
    SQLModel.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
