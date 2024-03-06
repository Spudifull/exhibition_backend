import logging

from pydantic import EmailStr

from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException
from starlette.status import HTTP_404_NOT_FOUND

from ..crud.user import retrieve_user_by_email, retrieve_user_by_id
from ..models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/{id}", response_model=User)
async def get_user_by_id(id: PydanticObjectId) -> User:
    logger.debug("The start of the GET_USER_by_ID route")

    user = await retrieve_user_by_id(id)
    if not user:
        logger.critical(f"The function route  has been error"
                        f"Failed to function GET_USER_BY_ID")

        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail=f"user with id: {id} not found"
        )

    logger.success("The route GET_USER_BY_ID has been successfully completed. "
                   "The request is being sent")

    return user


@router.get("/by_email/{email}", response_model=User)
async def get_user_by_email(email: EmailStr) -> User:
    logger.debug("The start of the GET_USER_by_EMAIL route")

    user = await retrieve_user_by_email(email)
    if not user:
        logger.critical(f"The function route  has been error"
                        f"Failed to function GET_USER_BY_ID. User has not been found with id %s" % (id,))

        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail=f"user with email: {email} not found"
        )

    logger.success("The route GET_USER_BY_ENAIL has been successfully completed. "
                   "The request is being sent")

    return user
