import logging

from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from ..config import settings
from ..models.estimate import Estimate
from ..models.floorplan_order import FloorplanOrder
from ..models.order import Order
from ..models.room import Room
from ..models.user import User
from .mongodb import db

log = logging.getLogger(__name__)


async def connect_to_mongo():
    db.client = AsyncIOMotorClient(settings.mongodb_url)
    await init_beanie(
        database=db.client[settings.database_name],
        document_models=[Order, Room, User, Estimate, FloorplanOrder],
    )
    logging.info("Connection is active")


async def close_mongo_connection():
    db.client.close()
    logging.info("Connection is closed")
