"""Cron Job template - scheduled task with error latch."""

import modal

MODAL_APP_NAME: str = "demo-cron-job"
MODAL_SECRET_NAME: str = MODAL_APP_NAME

app: modal.App = modal.App(MODAL_APP_NAME)
image: modal.Image = modal.Image.debian_slim().uv_pip_install("httpx")
state: modal.Dict = modal.Dict.from_name(f"{MODAL_APP_NAME}-state", create_if_missing=True)


def _has_error() -> bool:
    try:
        return bool(state["has_error"])
    except KeyError:
        return False


@app.function(
    image=image,
    schedule=modal.Period(
        seconds=60
    ),  # Period(minutes=15), Period(hours=4), Period(days=1), or modal.Cron("0 * * * *")
    max_containers=1,
    secrets=[modal.Secret.from_name(MODAL_SECRET_NAME)],
)
def run() -> None:
    if _has_error():
        return
    try:
        pass  # business logic
    except Exception:
        state["has_error"] = True
        raise


@app.local_entrypoint()
def reset() -> None:
    state["has_error"] = False
