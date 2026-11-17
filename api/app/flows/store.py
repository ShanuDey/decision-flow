"""Persistence for flows and runs. Tests swap this class for an in-memory fake."""

import uuid
from typing import Annotated, Any

from fastapi import Depends
from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.flows.models import Flow, FlowVersion
from app.workspaces.schemas import Member

LIVE = Flow.deleted_at.is_(None)
SORTABLE = {"name": Flow.name, "created_at": Flow.created_at, "updated_at": Flow.updated_at}


class PublishRefused(Exception):
    pass


class FlowMissing(PublishRefused):
    pass


class DraftMoved(PublishRefused):
    pass


class AlreadyPublished(PublishRefused):
    pass


class FlowStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_flow(self, member: Member, name: str, draft: dict[str, Any]) -> Flow:
        flow = Flow(
            workspace_id=member.workspace_id,
            created_by=member.user_id,
            updated_by=member.user_id,
            name=name,
            draft=draft,
        )
        self.session.add(flow)
        await self.session.commit()
        await self.session.refresh(flow)
        return flow

    async def count_flows(self, member: Member) -> int:
        return (
            await self.session.scalar(
                select(func.count())
                .select_from(Flow)
                .where(
                    Flow.workspace_id == member.workspace_id,
                    Flow.created_by == member.user_id,
                    LIVE,
                )
            )
            or 0
        )

    async def list_flows(
        self, member: Member, q: str | None, sort: str, page: int, page_size: int
    ) -> tuple[list[Flow], int]:
        column = SORTABLE[sort.lstrip("-")]
        query = select(Flow).where(Flow.workspace_id == member.workspace_id, LIVE)
        if q:
            query = query.where(Flow.name.icontains(q, autoescape=True))  # % and _ stay literal
        total = await self.session.scalar(select(func.count()).select_from(query.subquery()))
        order = column.desc() if sort.startswith("-") else column.asc()
        rows = await self.session.scalars(
            query.order_by(order, Flow.id).offset((page - 1) * page_size).limit(page_size)
        )
        return list(rows), total or 0

    async def get_flow(self, member: Member, flow_id: uuid.UUID) -> Flow | None:
        return await self.session.scalar(
            select(Flow).where(Flow.id == flow_id, Flow.workspace_id == member.workspace_id, LIVE)
        )

    async def list_callers(self, member: Member, flow_id: uuid.UUID) -> list[Flow]:
        """Live flows whose latest published version has a Subflow node that calls this one."""
        calls = {"nodes": [{"type": "subflow", "data": {"flow_id": str(flow_id)}}]}
        rows = await self.session.scalars(
            select(Flow)
            .join(
                FlowVersion,
                and_(FlowVersion.flow_id == Flow.id, FlowVersion.version == Flow.published_version),
            )
            .where(
                Flow.workspace_id == member.workspace_id,
                Flow.id != flow_id,
                LIVE,
                FlowVersion.deleted_at.is_(None),
                FlowVersion.graph.contains(calls),
            )
            .order_by(Flow.name, Flow.id)
        )
        return list(rows)

    async def rename_flow(self, member: Member, flow_id: uuid.UUID, name: str) -> Flow | None:
        result = await self.session.execute(
            update(Flow)
            .where(Flow.id == flow_id, Flow.workspace_id == member.workspace_id, LIVE)
            .values(name=name, updated_by=member.user_id, updated_at=func.now())
            .returning(Flow)
            .execution_options(populate_existing=True)
        )
        flow = result.scalar_one_or_none()
        await self.session.commit()
        return flow

    async def delete_flow(self, member: Member, flow_id: uuid.UUID, *, soft: bool) -> bool:
        """Soft marks the flow deleted and keeps its row, versions and runs."""
        live = (Flow.id == flow_id, Flow.workspace_id == member.workspace_id, LIVE)
        if soft:
            statement = (
                update(Flow)
                .where(*live)
                .values(deleted_at=func.now(), deleted_by=member.user_id)
                .returning(Flow.id)
            )
        else:
            statement = delete(Flow).where(*live).returning(Flow.id)
        result = await self.session.execute(statement)
        deleted = result.scalar_one_or_none()
        await self.session.commit()
        return deleted is not None

    async def save_draft(
        self, member: Member, flow_id: uuid.UUID, draft: dict[str, Any], expected_version: int
    ) -> Flow | None:
        """None when the version is stale (or the flow is gone): the caller tells them apart."""
        result = await self.session.execute(
            update(Flow)
            .where(
                Flow.id == flow_id,
                Flow.workspace_id == member.workspace_id,
                Flow.draft_version == expected_version,
                LIVE,
            )
            .values(
                draft=draft,
                draft_version=Flow.draft_version + 1,
                updated_by=member.user_id,
                updated_at=func.now(),
            )
            .returning(Flow)
            .execution_options(populate_existing=True)
        )
        flow = result.scalar_one_or_none()
        await self.session.commit()
        return flow

    async def publish(
        self,
        member: Member,
        flow_id: uuid.UUID,
        expected_draft_version: int,
        keep_versions: int = 0,
        *,
        soft: bool,
    ) -> FlowVersion:
        """Raises a PublishRefused subclass instead of returning when it cannot publish."""
        flow = await self.session.scalar(
            select(Flow)
            .where(Flow.id == flow_id, Flow.workspace_id == member.workspace_id, LIVE)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        refusal: PublishRefused | None = None
        if flow is None:
            refusal = FlowMissing()
        elif flow.draft_version != expected_draft_version:
            refusal = DraftMoved()
        elif flow.published_draft_version == flow.draft_version:
            refusal = AlreadyPublished()
        if refusal is not None or flow is None:
            await self.session.rollback()
            raise refusal or FlowMissing()
        version = FlowVersion(
            flow_id=flow.id,
            version=(flow.published_version or 0) + 1,
            graph=flow.draft,
            source_draft_version=flow.draft_version,
            created_by=member.user_id,
        )
        self.session.add(version)
        if keep_versions:
            old = (
                FlowVersion.flow_id == flow.id,
                FlowVersion.version <= version.version - keep_versions,
                FlowVersion.deleted_at.is_(None),
            )
            if soft:
                await self.session.execute(
                    update(FlowVersion)
                    .where(*old)
                    .values(deleted_at=func.now(), deleted_by=member.user_id)
                )
            else:
                await self.session.execute(delete(FlowVersion).where(*old))
        flow.published_version = version.version
        flow.published_draft_version = flow.draft_version
        flow.published_at = func.now()
        await self.session.commit()
        await self.session.refresh(version)
        await self.session.refresh(flow)
        return version

    async def list_versions(self, member: Member, flow_id: uuid.UUID) -> list[FlowVersion]:
        rows = await self.session.scalars(
            select(FlowVersion)
            .join(Flow, Flow.id == FlowVersion.flow_id)
            .where(
                FlowVersion.flow_id == flow_id,
                Flow.workspace_id == member.workspace_id,
                LIVE,
                FlowVersion.deleted_at.is_(None),
            )
            .order_by(FlowVersion.version.desc())
        )
        return list(rows)

    async def get_version(
        self, member: Member, flow_id: uuid.UUID, version: int
    ) -> FlowVersion | None:
        return await self.session.scalar(
            select(FlowVersion)
            .join(Flow, Flow.id == FlowVersion.flow_id)
            .where(
                FlowVersion.flow_id == flow_id,
                FlowVersion.version == version,
                Flow.workspace_id == member.workspace_id,
                LIVE,
                FlowVersion.deleted_at.is_(None),
            )
        )


def get_store(session: Annotated[AsyncSession, Depends(get_session)]) -> FlowStore:
    return FlowStore(session)
