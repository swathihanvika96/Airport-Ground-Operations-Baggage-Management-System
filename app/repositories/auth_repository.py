from sqlalchemy import select, update

from app.models.password_reset import PasswordResetToken
from app.repositories.base import BaseRepository
from app.utils.datetime_utils import utcnow


class AuthRepository(BaseRepository[PasswordResetToken]):
    model = PasswordResetToken
    entity_name = "Password reset token"

    def get_valid_token(self, token_hash: str) -> PasswordResetToken | None:
        return self.db.scalar(select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > utcnow(),
        ))

    def invalidate_user_tokens(self, user_id: int) -> None:
        self.db.execute(update(PasswordResetToken)
                        .where(PasswordResetToken.user_id == user_id, PasswordResetToken.used_at.is_(None))
                        .values(used_at=utcnow()))
