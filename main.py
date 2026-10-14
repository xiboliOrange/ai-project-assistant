from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from src.project_assistant.api.files import repository, router as files_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    repository.initialize()
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(files_router)


@app.exception_handler(HTTPException)
async def handle_http_error(_request: Request, error: HTTPException):
    if isinstance(error.detail, dict) and "error_code" in error.detail:
        return JSONResponse(status_code=error.status_code, content=error.detail)
    return JSONResponse(status_code=error.status_code, content={"detail": error.detail})


@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/")
def root():
    return {"message": "AI Project Assistant is running"}
