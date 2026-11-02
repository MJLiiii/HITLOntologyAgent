from contextlib import asynccontextmanager
import logging
from pathlib import Path
from threading import Event, Thread
from uuid import uuid4
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from .auth import bootstrap_token, init_cookie
from .errors import Problem
from . import responses as wire
from .settings import Settings
from .request_limits import RequestBodyLimit
from .workflow import Studio
from .api import sessions, health, projects, sources, proposals, experiments, jobs


def create_app(settings=None):
    settings = settings or Settings()
    studio = Studio(settings)
    stopping = Event()

    @asynccontextmanager
    async def lifespan(app):
        thread = None
        if settings.mode == 'local' and not settings.eager_jobs:
            logging.getLogger("uvicorn.error").info("Local operator link (keep private): http://127.0.0.1:8000/#session=%s", app.state.bootstrap_token)
        if settings.embedded_worker and not settings.eager_jobs:
            from .worker import run_worker
            thread = Thread(target=run_worker, args=(studio, stopping), daemon=True, name="ontology-worker")
            thread.start()
        yield
        stopping.set()
        if thread:
            thread.join(timeout=2)

    app = FastAPI(title="Ontology Studio API", version="0.1.0", lifespan=lifespan,
                  responses={status: {"model": wire.ProblemResponse} for status in (401, 403, 404, 409, 413, 422, 429, 504)})
    app.state.settings, app.state.studio = settings, studio
    app.state.local_cookie = init_cookie(settings.data_dir) if settings.mode == 'local' else None
    app.state.bootstrap_token = bootstrap_token(settings.data_dir) if settings.mode == 'local' else None

    @app.exception_handler(Problem)
    async def problem_handler(request, exc):
        return JSONResponse(status_code=exc.status, content={"code": exc.code, "message": exc.message, "details": exc.details, "correlation_id": str(uuid4())})

    @app.exception_handler(ValueError)
    async def value_error(request, exc):
        return JSONResponse(status_code=422, content={"code": "invalid_content", "message": str(exc)[:500], "details": None, "correlation_id": str(uuid4())})

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse(status_code=422, content={"code": "invalid_request", "message": "Request does not match the API schema", "details": [{"location": list(e["loc"]), "message": e["msg"]} for e in exc.errors()], "correlation_id": str(uuid4())})

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    app.add_middleware(RequestBodyLimit, limit=settings.max_upload_bytes + 65536)

    for routes in (sessions, health, projects, sources, proposals, experiments, jobs):
        app.include_router(routes.router)

    root = Path(__file__).resolve().parents[4]
    web = root / "apps/studio-plugin/dist"
    if web.exists():
        app.mount("/", StaticFiles(directory=web, html=True), name="studio")
    return app


app = create_app()
