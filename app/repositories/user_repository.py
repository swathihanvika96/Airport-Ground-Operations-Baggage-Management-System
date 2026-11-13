from sqlalchemy import func, or_, select

from app.models.user import User
from app.repositories.base import BaseRepository
from app.utils.enums import UserRole


class UserRepository(BaseRepository[User]):
    model = User
    entity_name = "User"

    def get_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(func.lower(User.email) == email.lower()))

    def get_by_login(self, login: str) -> User | None:
        return self.db.scalar(select(User).where(or_(func.lower(User.email) == login.lower(), User.username == login)))

    def get_by_oauth(self, provider, subject: str) -> User | None:
        return self.db.scalar(select(User).where(User.auth_provider == provider, User.oauth_subject == subject))

    def active_ids_by_roles(self, roles: list[UserRole] | None) -> list[int]:
        stmt = select(User.id).where(User.is_active.is_(True))
        if roles:
            stmt = stmt.where(User.role.in_(roles))
        return list(self.db.scalars(stmt).all())

    def search(self, q: str | None = None, role: UserRole | None = None, is_active: bool | None = None):
        stmt = select(User)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(User.email.ilike(like), User.full_name.ilike(like), User.username.ilike(like)))
        if role:
            stmt = stmt.where(User.role == role)
        if is_active is not None:
            stmt = stmt.where(User.is_active.is_(is_active))
        return stmt
