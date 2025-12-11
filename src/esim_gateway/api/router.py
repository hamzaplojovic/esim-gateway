from fastapi import APIRouter

from esim_gateway.api.catalog import router as catalog_router
from esim_gateway.api.orders import router as orders_router
from esim_gateway.api.esims import router as esims_router
from esim_gateway.api.account import router as account_router

api_router = APIRouter()

# Note: Health endpoint is defined in main.py without auth requirement
api_router.include_router(catalog_router)
api_router.include_router(orders_router)
api_router.include_router(esims_router)
api_router.include_router(account_router)
