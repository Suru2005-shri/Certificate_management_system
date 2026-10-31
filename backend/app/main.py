import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from . import db, routes_common, routes_hod, routes_student, routes_teacher, storage

log = logging.getLogger("portal")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.open_pool()
    try:
        storage.ensure_bucket()
    except Exception:
        log.warning("MinIO not reachable at startup; uploads will fail until it is available")
    yield
    db.close_pool()


app = FastAPI(title="Certificate Portal API", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
for r in (routes_common.router, routes_student.router, routes_teacher.router, routes_hod.router):
    app.include_router(r)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("Unhandled error on %s %s", request.method, request.url.path)   # no request bodies / tokens are logged
    return JSONResponse({"detail": "Something went wrong. Please try again."}, status_code=500)
