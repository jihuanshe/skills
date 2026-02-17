"""GPU Service template

GPU: "any"(L4/A10/T4), "L4", "L40S", "A100", "A100-80GB", "H100"
Region: "jp"(Japan), "kr"(Korea), "au"(Australia), "us-east", "eu-west"
"""

from typing import Any

import modal

MODAL_APP_NAME: str = "demo-gpu-service"
MODAL_SECRET_NAME: str = MODAL_APP_NAME
GPU: str = "any"  # <7B params

app: modal.App = modal.App(MODAL_APP_NAME)
image: modal.Image = modal.Image.debian_slim().uv_pip_install("torch", "fastapi[standard]")


@app.function(image=image)
@modal.fastapi_endpoint(method="GET")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.cls(
    image=image,
    gpu=GPU,
    max_containers=1,
    scaledown_window=300,
)
@modal.concurrent(max_inputs=32)
class GPUService:
    @modal.enter()
    def startup(self) -> None:
        import torch

        print(f"[GPU CHECK] cuda={torch.cuda.is_available()}")
        assert torch.cuda.is_available(), "GPU not available"

    @modal.method()
    def process(self, data: str) -> dict[str, Any]:
        return {"input": data, "status": "done"}


@app.local_entrypoint()
def test() -> None:
    print(GPUService().process.remote("test"))
