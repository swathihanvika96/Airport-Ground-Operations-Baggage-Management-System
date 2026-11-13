from sqlalchemy import select

from app.models.terminal import Terminal
from app.repositories.base import BaseRepository


class TerminalRepository(BaseRepository[Terminal]):
    model = Terminal
    entity_name = "Terminal"

    def search(self, airport_id=None, status=None):
        stmt = select(Terminal)
        if airport_id:
            stmt = stmt.where(Terminal.airport_id == airport_id)
        if status:
            stmt = stmt.where(Terminal.status == status)
        return stmt
