from fastapi import APIRouter

from api.routes import news, socmed

api_router = APIRouter()
api_router.include_router(news.router, prefix='/news')
api_router.include_router(socmed.router, prefix='/socmed')