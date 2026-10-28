import base64
import json
import re
from typing import Protocol, TypeVar

import httpx
import openai
from fastapi import Request
from pydantic import BaseModel, ValidationError

from backend.ai.prompts import ATTRIBUTE_SYSTEM_PROMPT, EDIT_SYSTEM_PROMPT
from backend.ai.schemas import Attributes, EditPlan
from backend.config import Settings
from backend.errors import AppError

CHAT_TIMEOUT = 30
IMAGE_TIMEOUT = 120
URL_FETCH_TIMEOUT = 60

M = TypeVar("M", bound=BaseModel)


class AIClient(Protocol):
    def extract_attributes(self, text: str) -> Attributes: ...
    def parse_edit(self, message: str, current: Attributes) -> EditPlan: ...
    def generate_image(self, prompt: str) -> bytes: ...
    def edit_image(self, image: bytes, prompt: str) -> bytes: ...


def extract_json(text: str) -> dict:
    """Return the first JSON object in text, tolerating code fences and surrounding prose."""
    decoder = json.JSONDecoder()
    for m in re.finditer(r"\{", text):
        try:
            obj, _ = decoder.raw_decode(text, m.start())
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    raise ValueError("no JSON object found in reply")


def _map_openai_error(e: Exception) -> AppError:
    if isinstance(e, openai.BadRequestError) and re.search(r"safety|policy|content", str(e), re.I):
        return AppError("AI_REFUSED", "The image service refused this request. Try rewording the description.", 422)
    return AppError("AI_UNAVAILABLE", "The AI service did not respond. Try again.", 503)


_RETRYABLE = (openai.APITimeoutError, openai.APIConnectionError, openai.InternalServerError)


class LiveAIClient:
    def __init__(self, settings: Settings, openai_client=None):
        self.s = settings
        self.client = openai_client or openai.OpenAI(
            base_url=settings.llm_base_url, api_key=settings.llm_api_key or "none", max_retries=0
        )

    def _call(self, fn, **kw):
        for attempt in range(2):
            try:
                return fn(**kw)
            except _RETRYABLE as e:
                if attempt == 1:
                    raise _map_openai_error(e)
            except openai.OpenAIError as e:
                raise _map_openai_error(e)

    def _chat(self, system: str, user: str) -> str:
        kw = dict(
            model=self.s.llm_chat_model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            timeout=CHAT_TIMEOUT,
        )
        try:
            r = self._call(self.client.chat.completions.create, response_format={"type": "json_object"}, **kw)
        except AppError:
            raise
        except openai.BadRequestError:
            r = self._call(self.client.chat.completions.create, **kw)
        return r.choices[0].message.content or ""

    def _structured(self, system: str, user: str, model_cls: type[M]) -> M:
        prompt = user
        for attempt in range(2):
            reply = self._chat(system, prompt)
            try:
                return model_cls.model_validate(extract_json(reply))
            except (ValueError, ValidationError) as e:
                prompt = f"{user}\n\nYour previous reply was invalid: {e}. Reply with only the corrected JSON object."
        raise AppError("AI_PARSE_FAILED", "The AI could not understand that. Try rephrasing.", 422)

    def extract_attributes(self, text: str) -> Attributes:
        return self._structured(ATTRIBUTE_SYSTEM_PROMPT, f"Witness description:\n{text}", Attributes)

    def parse_edit(self, message: str, current: Attributes) -> EditPlan:
        user = f"Current attributes:\n{current.model_dump_json()}\n\nWitness request:\n{message}"
        return self._structured(EDIT_SYSTEM_PROMPT, user, EditPlan)

    def _image_bytes(self, resp) -> bytes:
        item = resp.data[0]
        if getattr(item, "b64_json", None):
            return base64.b64decode(item.b64_json)
        r = httpx.get(item.url, timeout=URL_FETCH_TIMEOUT)
        r.raise_for_status()
        return r.content

    def _image_kw(self, prompt: str) -> dict:
        return dict(
            model=self.s.llm_image_model,
            prompt=prompt,
            size=self.s.llm_image_size,
            quality=self.s.llm_image_quality,
            n=1,
            timeout=IMAGE_TIMEOUT,
        )

    def generate_image(self, prompt: str) -> bytes:
        return self._image_bytes(self._call(self.client.images.generate, **self._image_kw(prompt)))

    def edit_image(self, image: bytes, prompt: str) -> bytes:
        resp = self._call(self.client.images.edit, image=("face.png", image, "image/png"), **self._image_kw(prompt))
        return self._image_bytes(resp)


def get_ai_client(request: Request) -> AIClient:
    return request.app.state.ai_client
