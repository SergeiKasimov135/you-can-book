import logging
import time

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.api.routers import auth, bookings, categories, events, feedback, friends, invitations, locations, users
from app.services import (
    AlreadyExistsError,
    BusinessRuleError,
    NotFoundError,
    PermissionDeniedError,
    ServiceError,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("api")

# Все адреса API начинаются с /api: так nginx отличает их от статики
app = FastAPI(
    title="You Can Book API",
    version="1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

for router in (auth, users, locations, categories, events, bookings, friends, invitations, feedback):
    app.include_router(router.router, prefix="/api")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Middleware: метод, путь, статус и время каждого запроса
    start = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - start) * 1000
    log.info("%s %s -> %s (%.0f ms)", request.method, request.url.path, response.status_code, ms)
    return response


# Ошибки сервисного слоя -> HTTP-статусы (сервисы про HTTP ничего не знают)
_STATUS = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    AlreadyExistsError: status.HTTP_409_CONFLICT,
    BusinessRuleError: status.HTTP_409_CONFLICT,
    PermissionDeniedError: status.HTTP_403_FORBIDDEN,
}


@app.exception_handler(ServiceError)
async def service_error_handler(request: Request, exc: ServiceError) -> JSONResponse:
    code = next((c for cls, c in _STATUS.items() if isinstance(exc, cls)), status.HTTP_400_BAD_REQUEST)
    return JSONResponse(status_code=code, content={"detail": str(exc)})


@app.get("/api/health", tags=["health"])
async def health():
    return {"status": "ok"}
