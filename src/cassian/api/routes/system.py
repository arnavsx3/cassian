from fastapi import APIRouter, Request

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/queue")
async def queue_config(request: Request) -> dict[str, str]:
    return {"backend": request.app.state.settings.queue_backend}


@router.get("/checkpoints")
async def checkpoint_config(request: Request) -> dict[str, str]:
    return {"backend": request.app.state.settings.checkpoint_backend}
