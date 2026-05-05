"""Plugin listing endpoint (the MVP returns an empty list)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.plugins import get_registry
from app.security import get_current_user

router = APIRouter(
    prefix="/api/plugins",
    tags=["plugins"],
    dependencies=[Depends(get_current_user)],
)


class PluginInfo(BaseModel):
    slug: str
    name: str
    version: str
    description: str
    requires_funpay_account: bool


@router.get("", response_model=list[PluginInfo])
def list_plugins() -> list[PluginInfo]:
    out: list[PluginInfo] = []
    for plugin in get_registry().all():
        m = plugin.manifest
        out.append(
            PluginInfo(
                slug=m.slug,
                name=m.name,
                version=m.version,
                description=m.description,
                requires_funpay_account=m.requires_funpay_account,
            )
        )
    return out
