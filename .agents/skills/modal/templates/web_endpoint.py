"""Web Endpoint template - simple HTTP endpoints (webhook + health)."""

from typing import Any

import modal

MODAL_APP_NAME: str = "demo-web-endpoint"
MODAL_SECRET_NAME: str = MODAL_APP_NAME

app: modal.App = modal.App(MODAL_APP_NAME)
image: modal.Image = modal.Image.debian_slim().uv_pip_install("fastapi[standard]", "httpx")


@app.function(image=image, secrets=[modal.Secret.from_name(MODAL_SECRET_NAME)])
@modal.fastapi_endpoint(method="GET")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.function(image=image, secrets=[modal.Secret.from_name(MODAL_SECRET_NAME)])
@modal.fastapi_endpoint(method="POST")
def webhook(payload: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "data": payload}
