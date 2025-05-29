from fastapi import FastAPI
from .endpoints.routers import node_router

# FastAPI initialization
app = FastAPI(
  title="Data Commons API",
  version="0.1.0",
  openapi_url="/openapi.json",
  docs_url="/docs",
  redoc_url="/redoc",
  debug=True
)

app.include_router(node_router.router, tags=["nodes"])
