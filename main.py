"""
Finance Tracker — Main Application Entry Point
A clean, production-quality FastAPI backend for personal finance management.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.database import engine
from app.models import Base  # imports all models so metadata is populated


# ── Lifespan: create DB tables on startup ────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create all database tables on startup if they don't exist."""
    Base.metadata.create_all(bind=engine)
    yield
    # Teardown (if needed in future)


# ── App factory ───────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="""
## Finance Tracker API

A production-quality backend for managing personal finances.

### Features
- 📊 **Transaction Management** — Create, view, update, and delete income/expense records
- 📈 **Analytics & Summaries** — Totals, category breakdowns, and monthly trends via SQL aggregations
- 👥 **Role-Based Access Control** — Viewer, Analyst, and Admin roles with scoped permissions
- 🔐 **JWT Authentication** — Secure token-based auth with 24-hour expiry
- ✅ **Strict Validation** — Pydantic v2 with meaningful error messages
- 💰 **Exact Money Storage** — Uses `Numeric(15,2)` to prevent float rounding errors

### Roles & Permissions
| Role | View | Create | Update | Delete | Admin |
|------|:----:|:------:|:------:|:------:|:-----:|
| `viewer` | ✅ | ❌ | ❌ | ❌ | ❌ |
| `analyst` | ✅ | ✅ | ✅ | ❌ | ❌ |
| `admin` | ✅ | ✅ | ✅ | ✅ | ✅ |

### Quick Start
1. Register via `POST /api/v1/auth/register`
2. Login via `POST /api/v1/auth/login` to receive a token
3. Click **Authorize** above and enter: `Bearer <your_token>`
4. Seed demo data via `POST /api/v1/admin/seed` (admin only)
    """,
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Global Exception Handlers ─────────────────────────────────────────────────

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Return consistent JSON error shape for all HTTP errors."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Return a clean, readable validation error response.
    Collapses Pydantic's nested error structure into a flat list.
    """
    errors = []
    for error in exc.errors():
        field = " → ".join(str(loc) for loc in error["loc"] if loc != "body")
        errors.append({
            "field": field or "body",
            "message": error["msg"].replace("Value error, ", ""),
            "type": error["type"],
        })
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation failed. Please check the fields below.",
            "errors": errors,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all for unexpected server errors — never leak stack traces."""
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An unexpected error occurred. Please try again or contact support.",
        },
    )


# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/", tags=["Root"], include_in_schema=False)
def root():
    """Health check and welcome endpoint."""
    return {
        "message": "Welcome to Finance Tracker API",
        "version": settings.VERSION,
        "docs": "/docs",
        "redoc": "/redoc",
        "status": "running",
    }


@app.get("/health", tags=["Root"], summary="Health check")
def health_check():
    """Simple liveness probe — returns 200 if the server is up."""
    return {"status": "healthy", "api_version": settings.VERSION}


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    """Suppress 404 noise in logs from browser favicon requests."""
    return JSONResponse(status_code=204, content=None)
