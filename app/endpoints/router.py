from fastapi import APIRouter
from .helpers import Helper

router = APIRouter()
helper = Helper(router)
