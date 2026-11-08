from fastapi import FastAPI

from app.assistant.router import router as assistant_router

app = FastAPI(
    title="NetSentry API",
    description="Network Configuration Auditing Platform",
    version="0.1.0",
)

app.include_router(assistant_router)


@app.get("/")
def root():
    return {
        "project": "NetSentry",
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "NetSentry API",
    }
