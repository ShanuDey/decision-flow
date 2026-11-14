import uuid

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Principal
from app.workspaces.models import User, Workspace, WorkspaceMember
from app.workspaces.schemas import Member

OWNER = "owner"


def workspace_name(principal: Principal) -> str:
    who = principal.name or (principal.email.split("@")[0] if principal.email else None)
    return f"{who[:100]}'s workspace" if who else "My workspace"


class WorkspaceStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def ensure_member(self, principal: Principal) -> Member:
        return (await self.create_member(principal))[0]

    async def create_member(self, principal: Principal) -> tuple[Member, bool]:
        """The caller's user and workspace, created together on their first request.

        The flag says whether this call created them, not a concurrent one.
        """
        member = await self.find_member(principal)
        if member is not None:
            return member, False
        created = await self._create(principal)
        member = await self.find_member(principal)
        if member is None:
            raise RuntimeError("user exists without a workspace")
        return member, created

    async def touch(self, user_id: uuid.UUID) -> None:
        await self.session.execute(
            update(User).where(User.id == user_id).values(last_seen_at=func.now())
        )
        await self.session.commit()

    async def find_member(self, principal: Principal) -> Member | None:
        row = (
            await self.session.execute(
                select(User.id, WorkspaceMember.workspace_id)
                .join(WorkspaceMember, WorkspaceMember.user_id == User.id)
                .where(User.provider == principal.provider, User.sub == principal.sub)
                .order_by(WorkspaceMember.created_at, WorkspaceMember.workspace_id)
                .limit(1)
            )
        ).first()
        return Member(user_id=row.id, workspace_id=row.workspace_id) if row else None

    async def _create(self, principal: Principal) -> bool:
        user_id = await self.session.scalar(
            insert(User)
            .values(
                id=uuid.uuid4(),
                provider=principal.provider,
                sub=principal.sub,
                email=principal.email,
                name=principal.name,
            )
            .on_conflict_do_nothing(index_elements=["provider", "sub"])
            .returning(User.id)
        )
        if user_id is None:  # a concurrent first request created the user and its workspace
            return False
        workspace = Workspace(id=uuid.uuid4(), name=workspace_name(principal))
        self.session.add_all(
            [workspace, WorkspaceMember(workspace_id=workspace.id, user_id=user_id, role=OWNER)]
        )
        await self.session.commit()
        return True
