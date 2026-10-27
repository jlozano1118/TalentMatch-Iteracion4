from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database.models import Project, Role


class ProjectRepository:
    def __init__(self, db: Session):
        self.db = db

    def all_with_roles(self) -> list[Project]:
        return list(self.db.scalars(select(Project).options(selectinload(Project.roles)).order_by(Project.id)))

    def roles(self) -> list[Role]:
        return list(self.db.scalars(select(Role).order_by(Role.project_id, Role.id)))

    def role(self, role_id: int) -> Role | None:
        return self.db.get(Role, role_id)

    def save_role(self, role: Role) -> Role:
        self.db.add(role)
        self.db.commit()
        return role
