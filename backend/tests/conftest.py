from __future__ import annotations

from pathlib import Path
import sys
import types


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
            pass

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

    class Request:
        scope: dict[str, object]

    class Response:
        def __init__(self):
            self.cookies: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

        def set_cookie(self, key: str, *args, **kwargs):
            self.cookies.append(("set", (key, *args), kwargs))

        def delete_cookie(self, key: str, *args, **kwargs):
            self.cookies.append(("delete", (key, *args), kwargs))

    class CORSMiddleware:
        pass

    class RedirectResponse:
        def __init__(self, *args, **kwargs):
            pass

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

    def _field(*args, **kwargs):
        return None

    pydantic_module.BaseModel = BaseModel
    pydantic_module.Field = _field
    sys.modules["pydantic"] = pydantic_module


try:
    import dotenv  # noqa: F401
except ModuleNotFoundError:
    dotenv_module = types.ModuleType("dotenv")
    dotenv_module.load_dotenv = lambda *args, **kwargs: None
    sys.modules["dotenv"] = dotenv_module


# Pre-emptively stub cryptography to avoid pyo3/cffi issues in test environments
# that have an incompatible system-level cryptography package.
if "cryptography.fernet" not in sys.modules:
    class _Fernet:
        def __init__(self, key: bytes):
            self._key = key

        @staticmethod
        def generate_key() -> bytes:
            return b"A" * 32

        def encrypt(self, data: bytes) -> bytes:
            return data

        def decrypt(self, token: bytes) -> bytes:
            return token

    class _InvalidToken(Exception):
        pass

    _crypto = types.ModuleType("cryptography")
    _fernet = types.ModuleType("cryptography.fernet")
    _fernet.Fernet = _Fernet
    _fernet.InvalidToken = _InvalidToken
    _exceptions = types.ModuleType("cryptography.exceptions")
    _exceptions.InvalidSignature = Exception
    _hazmat = types.ModuleType("cryptography.hazmat")
    _bindings = types.ModuleType("cryptography.hazmat.bindings")
    _rust = types.ModuleType("cryptography.hazmat.bindings._rust")

    sys.modules.setdefault("cryptography", _crypto)
    sys.modules["cryptography.fernet"] = _fernet
    sys.modules["cryptography.exceptions"] = _exceptions
    sys.modules["cryptography.hazmat"] = _hazmat
    sys.modules["cryptography.hazmat.bindings"] = _bindings
    sys.modules["cryptography.hazmat.bindings._rust"] = _rust
