from fastapi import APIRouter, Request

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/queue")
async def queue_config(request: Request) -> dict[str, str]:
    settings = request.app.state.settings
    return {"backend": settings.queue_backend}


@router.get("/checkpoints")
async def checkpoint_config(request: Request) -> dict[str, str]:
    settings = request.app.state.settings
    return {"backend": settings.checkpoint_backend}


@router.get("/runtime")
async def runtime_config(request: Request) -> dict[str, str | bool]:
    settings = request.app.state.settings
    return {
        "queue_backend": settings.queue_backend,
        "checkpoint_backend": settings.checkpoint_backend,
        "embedded_worker_enabled": settings.embedded_worker_enabled,
        "worker_execution_mode": settings.worker_execution_mode,
        "aws_enabled": settings.aws_enabled,
    }
