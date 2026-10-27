from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import User


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email.lower().strip()))

    def by_id(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def save(self, user: User) -> User:
        self.db.add(user)
        self.db.commit()
        return user
