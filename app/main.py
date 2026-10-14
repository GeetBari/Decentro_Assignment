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
            "## Start here\n\n"
            "Use the [plain-English API guide](/api-guide) if you are new to the project. "
            "This page is the interactive reference for testing individual endpoints.\n\n"
            "### Recommended order\n\n"
            "1. Create people with **Users**.\n"
            "2. Create a group, then add those people as **Group members**.\n"
            "3. Add an **Expense**. Omit `splits` for an equal split, or provide exact custom shares.\n"
            "4. Check **Balances** and **Settlement suggestions**.\n"
            "5. Record a **Settlement** after money has actually been paid.\n\n"
            'All amounts are INR decimal strings such as `"1200.00"`. This demo has no authentication.'
        ),
        openapi_tags=[
            {"name": "Start here", "description": "A quick health check for the running service."},
            {"name": "1. People", "description": "Create people before adding them to a group."},
            {
                "name": "2. Groups",
                "description": "Create groups and decide who shares future expenses.",
            },
            {
                "name": "3. Expenses",
                "description": "Record bills and split them equally or by custom amounts.",
            },
            {
                "name": "4. Settle up",
                "description": "See balances, get suggested payments, and record repayments.",
            },
        ],
    )
    app.state.engine = engine
    static_directory = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static_directory), name="static")

    @app.get("/", include_in_schema=False)
    def dashboard():
        return FileResponse(static_directory / "index.html")

    @app.get("/api-guide", include_in_schema=False)
    def api_guide():
        return FileResponse(static_directory / "api-guide.html")

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
