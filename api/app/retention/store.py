"""Bulk deletes for retention. Cutoffs are computed in SQL so the clocks cannot disagree."""

import uuid
from datetime import timedelta

from sqlalchemy import ARRAY, Select, String, bindparam, delete, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.base import FrozenBaseModel
from app.runs.models import Run
from app.workspaces.models import User, Workspace, WorkspaceMember

BATCH = 500
WEB_PROVIDER = "web"
AUTH_SESSION_TABLE = "auth.session"
AUTH_USER_TABLES = (("session", '"userId"'), ("account", '"userId"'), ('"user"', "id"))


class InactiveUser(FrozenBaseModel):
    id: uuid.UUID
    provider: str
    sub: str


class RetentionStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def delete_runs_older_than(self, days: int, dry_run: bool = False) -> int:
        old = Run.started_at < func.now() - timedelta(days=days)
        if dry_run:
            return await self.session.scalar(select(func.count()).where(old)) or 0
        total = 0
        while True:
            ids = select(Run.id).where(old).limit(BATCH)
            statement = delete(Run).where(Run.id.in_(ids)).returning(Run.id)
            result = await self.session.execute(statement)
            deleted = len(result.all())
            await self.session.commit()
            total += deleted
            if deleted < BATCH:
                return total

    async def delete_inactive_users(
        self, days: int, keep_emails: list[str], dry_run: bool = False
    ) -> int:
        if dry_run:
            return await self._count_inactive(days, keep_emails)
        total = 0
        while users := await self._inactive(days, keep_emails):
            await self._delete(users)
            total += len(users)
        return total

    def _inactive_query(
        self, days: int, keep_emails: list[str]
    ) -> Select[tuple[uuid.UUID, str, str]]:
        query = select(User.id, User.provider, User.sub).where(
            User.last_seen_at < func.now() - timedelta(days=days)
        )
        if keep_emails:
            # a NULL email is never on the list, and `NOT IN` would drop it
            query = query.where(
                or_(User.email.is_(None), func.lower(User.email).not_in(keep_emails))
            )
        return query

    async def _inactive(self, days: int, keep_emails: list[str]) -> list[InactiveUser]:
        # Locked until the delete commits, so a request cannot refresh the user mid-delete.
        query = self._inactive_query(days, keep_emails).limit(BATCH)
        query = query.with_for_update(skip_locked=True)
        rows = await self.session.execute(query)
        return [InactiveUser(id=r.id, provider=r.provider, sub=r.sub) for r in rows]

    async def _count_inactive(self, days: int, keep_emails: list[str]) -> int:
        query = self._inactive_query(days, keep_emails).subquery()
        return await self.session.scalar(select(func.count()).select_from(query)) or 0

    async def _delete(self, users: list[InactiveUser]) -> None:
        ids = [u.id for u in users]
        # Their workspace goes first: it cascades members, flows and runs, which restrict the user.
        workspaces = select(WorkspaceMember.workspace_id).where(WorkspaceMember.user_id.in_(ids))
        await self.session.execute(delete(Workspace).where(Workspace.id.in_(workspaces)))
        await self.session.execute(delete(User).where(User.id.in_(ids)))
        web_ids = [u.sub for u in users if u.provider == WEB_PROVIDER]
        if web_ids and await self.auth_schema_exists():
            subs = bindparam("subs", web_ids, type_=ARRAY(String))
            for table, column in AUTH_USER_TABLES:
                await self.session.execute(
                    text(f"delete from auth.{table} where {column} = any(:subs)").bindparams(subs)
                )
        await self.session.commit()

    async def delete_expired_auth_sessions(self, dry_run: bool = False) -> int:
        if not await self.auth_schema_exists():
            return 0
        if dry_run:
            sql = 'select count(*) from auth.session where "expiresAt" < now()'
        else:
            sql = (
                'with d as (delete from auth.session where "expiresAt" < now() returning 1) '
                "select count(*) from d"
            )
        count = await self.session.scalar(text(sql))
        await self.session.commit()
        return count or 0

    async def auth_schema_exists(self) -> bool:
        found = await self.session.scalar(
            text("select to_regclass(:name) is not null"), {"name": AUTH_SESSION_TABLE}
        )
        return bool(found)
