from fastapi import FastAPI

app = FastAPI(
    title="NetSentry API",
    description="Network Configuration Auditing Platform",
    version="0.1.0",
)


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
