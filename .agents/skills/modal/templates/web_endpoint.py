"""Web Endpoint template - ASGI app with health + webhook routes.

Uses @modal.asgi_app() with a FastAPI instance for path-based routing.
All endpoints share a single URL (e.g., https://...modal.run/health).
"""

from typing import Any

import modal

MODAL_APP_NAME: str = "demo-web-endpoint"
MODAL_SECRET_NAME: str = MODAL_APP_NAME

app: modal.App = modal.App(MODAL_APP_NAME)
image: modal.Image = modal.Image.debian_slim().uv_pip_install("fastapi[standard]", "httpx")


def create_fastapi_app():
    from fastapi import FastAPI

    web_app = FastAPI()

    @web_app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @web_app.post("/webhook")
    def webhook(payload: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "data": payload}

    return web_app


@app.function(image=image, secrets=[modal.Secret.from_name(MODAL_SECRET_NAME)])
@modal.asgi_app()
def web():
    return create_fastapi_app()
