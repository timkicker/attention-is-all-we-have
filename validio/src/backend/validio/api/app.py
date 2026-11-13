from contextlib import asynccontextmanager

from fastapi import FastAPI

from validio.api.steady import router as steady_router
from validio.policy.decide import load_policy, policy_file


@asynccontextmanager
async def lifespan(_app: FastAPI):
    load_policy(policy_file())  # a broken policy file stops the app, never a silent rule change
    yield


app = FastAPI(title="Validio", version="0.1.0", lifespan=lifespan)
app.include_router(steady_router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
