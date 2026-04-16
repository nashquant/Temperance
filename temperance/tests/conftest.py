from __future__ import annotations

from pathlib import Path
import sys
import types

import pytest


ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


try:
    import fastapi  # noqa: F401
except ModuleNotFoundError:
    fastapi_module = types.ModuleType("fastapi")
    middleware_module = types.ModuleType("fastapi.middleware")
    cors_module = types.ModuleType("fastapi.middleware.cors")
    responses_module = types.ModuleType("fastapi.responses")

    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str | None = None):
            super().__init__(detail or "")
            self.status_code = status_code
            self.detail = detail

    class FastAPI:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def add_middleware(self, *args, **kwargs):
            return None

        def middleware(self, *args, **kwargs):
            def decorator(fn):
                return fn

            return decorator

        def on_event(self, *args, **kwargs):
            def decorator(fn):
                return fn

            return decorator

        def post(self, *args, **kwargs):
            def decorator(fn):
                return fn

            return decorator

        def get(self, *args, **kwargs):
            def decorator(fn):
                return fn

            return decorator

        def put(self, *args, **kwargs):
            def decorator(fn):
                return fn

            return decorator

        def delete(self, *args, **kwargs):
            def decorator(fn):
                return fn

            return decorator

        def patch(self, *args, **kwargs):
            def decorator(fn):
                return fn

            return decorator

    def _identity(value=None, **kwargs):
        return value

    class Request:  # pragma: no cover - test stub only
        scope: dict[str, object]

    class Response:  # pragma: no cover - test stub only
        def __init__(self):
            self.cookies: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

        def set_cookie(self, key: str, *args, **kwargs):
            self.cookies.append(("set", (key, *args), kwargs))

        def delete_cookie(self, key: str, *args, **kwargs):
            self.cookies.append(("delete", (key, *args), kwargs))

    class CORSMiddleware:  # pragma: no cover - test stub only
        pass

    class RedirectResponse:  # pragma: no cover - test stub only
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    fastapi_module.FastAPI = FastAPI
    fastapi_module.Header = _identity
    fastapi_module.HTTPException = HTTPException
    fastapi_module.Query = _identity
    fastapi_module.Request = Request
    fastapi_module.Response = Response
    cors_module.CORSMiddleware = CORSMiddleware
    responses_module.RedirectResponse = RedirectResponse

    sys.modules["fastapi"] = fastapi_module
    sys.modules["fastapi.middleware"] = middleware_module
    sys.modules["fastapi.middleware.cors"] = cors_module
    sys.modules["fastapi.responses"] = responses_module


try:
    import pydantic  # noqa: F401
except ModuleNotFoundError:
    pydantic_module = types.ModuleType("pydantic")

    class BaseModel:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    pydantic_module.BaseModel = BaseModel
    sys.modules["pydantic"] = pydantic_module


try:
    import dotenv  # noqa: F401
except ModuleNotFoundError:
    dotenv_module = types.ModuleType("dotenv")
    dotenv_module.load_dotenv = lambda *args, **kwargs: None
    sys.modules["dotenv"] = dotenv_module


@pytest.fixture(autouse=True)
def _reset_auth_users_cache() -> None:
    """Reset the auth user cache between tests so monkeypatch env changes take effect."""
    try:
        import backend.app.main as _main

        _main._AUTH_USERS_CACHE = None
    except Exception:
        pass
