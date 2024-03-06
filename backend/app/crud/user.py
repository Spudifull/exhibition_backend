import logging

from pydantic import EmailStr

from beanie import PydanticObjectId

from ..models.user import User

logger = logging.getLogger(__name__)


async def retrieve_user_by_id(user_id: PydanticObjectId):
    logger.debug("retrieve_user_by_id calling")
    return await User.get(user_id)


async def retrieve_user_by_email(email: EmailStr):
    logger.debug("retrieve_user_by_email calling")
    return await User.find_one(User.email == email)
