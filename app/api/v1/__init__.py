from fastapi import APIRouter

from app.api.v1.articles import router as articles_router
from app.api.v1.auth import router as auth_router
from app.api.v1.sync import router as sync_router
from app.api.v1.trends import router as trends_router
from app.api.v1.ws import router as ws_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(articles_router)
api_router.include_router(trends_router)
api_router.include_router(sync_router)
api_router.include_router(ws_router)
