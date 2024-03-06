import logging
from typing import Optional

from pydantic import HttpUrl

from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException
from starlette.status import (HTTP_201_CREATED,
                              HTTP_404_NOT_FOUND,
                              HTTP_500_INTERNAL_SERVER_ERROR)

from ..crud.room import retrieve_order_preview_url, retrieve_order_rooms
from ..crud.order import retrieve_order_by_id
from ..crud.user import retrieve_user_by_id
from ..models.area import AreaIn
from ..models.room import Room
from ..utils.url import UrlBuilder
from ..s3.file_ops import create_json_file

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orders", tags=["Rooms"])


@router.get("/{id}/rooms", response_model=list[Room], summary="Get Rooms in Order")
async def get_rooms_in_order(id: PydanticObjectId) -> list[Room]:
    logger.debug("The start of the GET_ORDER_AND_USER_BY_ID route")

    try:
        return await retrieve_order_rooms(id)

    except Exception as e:
        logger.critical("An error occurred during the operation of the route"
                        "GET_ROOMS_IN_ORDER. DETAILS: {}".format(e))

        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,

        )


@router.post(
    "/{id}/rooms/{room_id}",
    status_code=HTTP_201_CREATED,
    summary="Upload Room JSON to S3",
    response_model=AreaIn)
async def post_room_area(id: PydanticObjectId, room_id: PydanticObjectId, area: AreaIn) -> AreaIn:
    logger.debug("The start of the POST_ROOM_AREA route")

    try:
        order = await retrieve_order_by_id(id)
        if order is None:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail=f"order with id: {id} not found"
            )
        user = await retrieve_user_by_id(order.userID)
        if user is None:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail=f"user with id: {order.userID} not found"
            )
        builder = UrlBuilder(user.identity, order.itemID)
        s3_path = builder.get_s3_json_path(f"{room_id}.json")
        await create_json_file(area.model_dump(by_alias=True), s3_path)

        logger.success("The route POST_ROOM_AREA has been successfully completed. "
                       "The request is being sent")

        return area
    except Exception as e:
        logger.critical("An error occurred during the operation of the function "
                        "POST_ROOM_AREA. DETAILS: {}".format(e))

        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to work for function POST_ROOM_AREA",
        )


@router.get(
    "/{id}/preview", response_model=Optional[HttpUrl], summary="Get Order Preview Url"
)
async def get_order_preview(id: PydanticObjectId) -> Optional[HttpUrl]:
    logger.debug("The start of the GET_ORDER_PREVIEW route")

    try:
        return await retrieve_order_preview_url(id)
    except Exception as e:
        logger.critical("An error occurred during the operation of the function "
                        "GET_ORDER_PREVIEW. DETAILS: {}".format(e))

        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to work for route GET_ORDER_PREVIEW",
        )
