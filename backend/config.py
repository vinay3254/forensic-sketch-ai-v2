from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    jwt_secret: str = Field(min_length=32)  # HS256 key; short secrets are brute-forceable
    jwt_expiry_hours: int = 8
    # creating an admin account at sign-up needs this code; empty turns admin sign-up off
    admin_signup_code: str = ""
    cookie_secure: bool = True
    database_url: str = "sqlite:///./app.db"
    storage_dir: Path = Path("./storage")
    frontend_origin: str = "http://localhost:5173"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_chat_model: str = ""
    llm_blender_model: str = ""  # connected coding/vision model; falls back to llm_chat_model
    blender_bin: str = "blender"  # packaged Blender executable for isolated background builds
    llm_image_model: str = ""
    llm_image_size: str = "1024x1536"
    llm_image_quality: str = "medium"
    # "images" = POST /images/edits; "responses" = /responses with the image_generation tool,
    # for providers (e.g. Codex via OmniRoute) whose image models cannot take an input image
    llm_image_edit_api: Literal["images", "responses"] = "images"
    llm_image_edit_model: str = ""  # text model that calls the tool; used only with "responses"
    # paste the old sketch back outside the edited regions; needs storage/models/face_parser.onnx
    # (scripts/fetch_face_parser.py), otherwise refines keep the raw edit
    edit_localize: bool = True
    # Local head and full-body reconstruction worker (head3d/server.py); empty disables both.
    head3d_url: str = ""
    # Blender figure worker (blender_worker/server.py), e.g. http://127.0.0.1:8020; empty turns it off
    figure_url: str = ""
    # Realistic body (backend/figure/realistic.py): MPFB2 and the pose model, fetched by
    # scripts/fetch_realistic_body.py into storage/realistic/; built with the blender_worker Python
    blender_python: str = "blender_worker/.venv/bin/python"
    ai_mock: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
