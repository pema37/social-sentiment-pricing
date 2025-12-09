from sqlmodel import SQLModel

from db.session import engine
from models.user import User  # noqa: F401


def init_db() -> None:
    SQLModel.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
