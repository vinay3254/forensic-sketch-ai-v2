from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from backend.ai.client import LiveAIClient
from backend.ai.mock import MockAIClient
from backend.audit.routes import router as audit_router
from backend.auth.ratelimit import LoginLimiter
from backend.auth.routes import router as auth_router
from backend.body.routes import router as body_router
from backend.body.types import router as body_types_router
from backend.cases.routes import router as cases_router
from backend.config import Settings, get_settings
from backend.db import init_db, make_engine
from backend.export.routes import router as export_router
from backend.face.regions import FaceParser
from backend.face.routes import router as face_router
from backend.head3d.client import HttpHead3DClient
from backend.head3d.routes import router as head3d_router
from backend.interview.routes import router as interview_router
from backend.sheet.routes import router as sheet_router
from backend.variants.routes import router as variants_router
from backend.errors import register_error_handlers


def make_face_parser(settings: Settings) -> FaceParser | None:
    path = settings.storage_dir / "models" / "face_parser.onnx"
    if settings.ai_mock or not settings.edit_localize or not path.is_file():
        return None
    return FaceParser(path)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db(app.state.engine)
        settings.storage_dir.mkdir(parents=True, exist_ok=True)
        yield

    app = FastAPI(title="AI Crime Scene Sketch Generator", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = make_engine(settings.database_url)
    app.state.login_limiter = LoginLimiter()
    app.state.ai_client = MockAIClient() if settings.ai_mock else LiveAIClient(settings)
    app.state.face_parser = make_face_parser(settings)
    app.state.head3d_client = HttpHead3DClient(settings.head3d_url) if settings.head3d_url else None

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    app.include_router(auth_router)
    app.include_router(audit_router)
    app.include_router(cases_router)
    app.include_router(face_router)
    app.include_router(export_router)
    app.include_router(interview_router)
    app.include_router(variants_router)
    app.include_router(body_router)
    app.include_router(body_types_router)
    app.include_router(sheet_router)
    app.include_router(head3d_router)

    @app.get("/health")
    def health():
        try:
            with app.state.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            db = "ok"
        except Exception:
            db = "error"
        return {
            "status": "ok",
            "db": db,
            "ai_mode": "mock" if settings.ai_mock else "live",
            "head3d": "on" if app.state.head3d_client else "off",
        }

    return app
