from fastapi import APIRouter

from app.features.conversational_agent.infrastructure.api.v1.endpoints import (
    chat,
    health,
)

router = APIRouter()
router.include_router(chat.router, prefix="/api/v1", tags=["chat"])
router.include_router(health.router, tags=["health"])
