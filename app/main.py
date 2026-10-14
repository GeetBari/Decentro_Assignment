import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError, OperationalError
from starlette.exceptions import HTTPException

from app.database import Base, make_engine
from app.routes import router
from app.schemas import ErrorResponse

logger = logging.getLogger(__name__)


def create_app(database_url: str | None = None) -> FastAPI:
    engine = make_engine(database_url or os.getenv("DATABASE_URL", "sqlite:///./expenses.db"))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        Base.metadata.create_all(engine)
        yield
        engine.dispose()

    app = FastAPI(
        title="Expense Sharing Service",
        version="1.0.0",
        lifespan=lifespan,
        description=(
            "Track INR group expenses, exact splits, balances, and settlements. "
            "Money responses are decimal strings. This is an assignment demo without authentication."
        ),
    )
    app.state.engine = engine
    static_directory = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static_directory), name="static")

    @app.get("/", include_in_schema=False)
    def dashboard():
        return FileResponse(static_directory / "index.html")

    app.include_router(
        router,
        responses={
            404: {"model": ErrorResponse, "description": "Resource not found"},
            409: {"model": ErrorResponse, "description": "Conflicting record"},
            422: {"model": ErrorResponse, "description": "Invalid request or business rule"},
            503: {"model": ErrorResponse, "description": "Database unavailable"},
        },
    )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"message": exc.detail}},
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        details = [
            {"field": ".".join(map(str, error["loc"])), "message": error["msg"]}
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422, content={"error": {"message": "Validation failed", "details": details}}
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error(request: Request, exc: IntegrityError):
        logger.warning("Database constraint rejected a write")
        return JSONResponse(
            status_code=409,
            content={"error": {"message": "The operation conflicts with existing records"}},
        )

    @app.exception_handler(OperationalError)
    async def database_error(request: Request, exc: OperationalError):
        logger.exception("Database operation failed")
        return JSONResponse(
            status_code=503, content={"error": {"message": "Database temporarily unavailable"}}
        )

    return app


app = create_app()
