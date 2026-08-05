from fastapi import APIRouter

from backend.app.core.config import settings


router = APIRouter(
    prefix="/health",
    tags=["Health"],
)


@router.get("")
async def health_check() -> dict[str, str]:
    """백엔드 서버의 실행 상태를 확인한다."""
    return {
        "status": "ok",
        "environment": settings.app_environment,
        "version": settings.app_version,
    }