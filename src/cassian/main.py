import uvicorn


def main() -> None:
    uvicorn.run("cassian.app:app", host="127.0.0.1", port=8000, reload=False)
