"""
Модуль содержащий объект маршрутизации на все endpoints
"""

from fastapi import APIRouter

from .helpers import Helper

router = APIRouter()
helper = Helper(router)
