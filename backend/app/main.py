from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.security import token_settings


def create_app() -> FastAPI:
    token_settings()
    app = FastAPI(
        title="SmartRecipe API",
        description="Backend API for the SmartRecipe application.",
        version="0.1.0",
    )
    app.include_router(health_router)
    app.include_router(auth_router)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request, exc):
        # Never echo request inputs, including malformed JSON containing secrets.
        errors = [{"loc": [part if isinstance(part, int) else "field"
                           for part in error["loc"]],
                   "msg": "Invalid request value", "type": "value_error"}
                  for error in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": errors})

    return app


app = create_app()
