import logging
import asyncio
from typing import Optional

from pydantic import HttpUrl

from beanie import PydanticObjectId

from ..models.order import Order, OrderWithRooms
from ..models.room import Room
from ..utils.url import ImageSize, UrlBuilder, check_url
from .user import retrieve_user_by_id

# TODO: figure out consistent log format
# TODO: add functions args to negative log events

logger = logging.getLogger(__name__)


async def retrieve_order_rooms(
        order_id: PydanticObjectId,
        url_check: bool = True
) -> list[Room]:
    logger.debug("retrieve_order_rooms calling")

    order = await Order.find_one(Order.id == order_id).project(OrderWithRooms)
    if not order:
        logger.error("Order is empty")

        return []

    user = await retrieve_user_by_id(order.userID)
    if not user or not order.itemID:
        return [room for room in order.panoramas]

    url_builder = UrlBuilder(user.identity, order.itemID)
    tasks = [process_room(room, url_builder, url_check) for room in order.panoramas]
    return list(await asyncio.gather(*tasks))


async def process_room(room: Room, url_builder: UrlBuilder, url_check: bool) -> Room:
    logger.debug("process_room calling")

    match url_check:
        case True:
            url = url_builder.get_external_json_url(f"{room.id}.json")

            if await check_url(url.unicode_string()):
                room.lineItemJsonUrl = url

    match room.filename:
        case None:
            pass

        case _:
            if room.filename:
                room.imgUrlFull = url_builder.get_img_url(ImageSize.size_full, room.filename)
                room.imgUrl150 = url_builder.get_img_url(ImageSize.size_150, room.filename)

    return room


async def retrieve_order_preview_url(order_id: PydanticObjectId) -> Optional[HttpUrl]:
    logger.debug("retrieve_order_preview_url calling")

    order = await Order.find_one(Order.id == order_id).project(OrderWithRooms)
    if not order:
        logger.info("Order is empty")
        return None

    if not (order.userID and order.itemID):
        logger.info(f"user: {order.userID} or item_id: {order.itemID} are empty")
        return None

    url_builder = UrlBuilder(order.userID, order.itemID)
    preview_url = next(
        (url_builder.get_img_url(ImageSize.size_150, room.filename) for room in order.panoramas if room.isFirst), None)

    if not preview_url:
        logger.info("IsFirst room has not been found")

    return preview_url
