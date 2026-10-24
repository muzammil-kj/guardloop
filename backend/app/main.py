from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ingestion.routes import router as ingestion_router
from app.api.events import router as events_router
from app.api.escalations import router as escalations_router
from app.api.costs import router as costs_router
from app.api.organizations import router as organizations_router
from app.api.policies import router as policies_router
from app.api.realtime import router as realtime_router
from app.api.alert_channels import router as alert_channels_router
from app.api.internal import router as internal_router
from app.api.judge import router as judge_router

app = FastAPI(title="Guardloop API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your Vercel domain once Phase 1 is confirmed working
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


app.include_router(organizations_router)
app.include_router(ingestion_router)
app.include_router(events_router)
app.include_router(escalations_router)
app.include_router(costs_router)
app.include_router(policies_router)
app.include_router(realtime_router)
app.include_router(alert_channels_router)
app.include_router(internal_router)
app.include_router(judge_router)
