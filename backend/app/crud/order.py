from datetime import datetime
import logging
import asyncio
from typing import Optional

from beanie import PydanticObjectId

from .user import retrieve_user_by_id
from ..models.order import Order, OrderId, OrderWithRooms, OrderWithPicture
from ..utils.url import UrlBuilder, ImageSize

log = logging.getLogger(__name__)


async def retrieve_orders(limit: int, offset: int) -> list[Order]:
    log.debug("retrieve_orders calling")
    return await Order.find_all().skip(offset).limit(limit).to_list()


async def transform_order_in_order_with_rooms(orders: list[Order]) -> list[OrderWithRooms]:
    log.debug("transform_order_in_order_with_rooms calling")

    order_ids = [order.id for order in orders]

    new_orders = await Order.find({"_id": {"$in": order_ids}}).project(OrderWithRooms).to_list()

    return new_orders


async def get_url_picture_orders(orders: list[Order]) -> list[OrderWithPicture]:
    log.debug("get_url_picture_orders calling")

    new_orders = await transform_order_in_order_with_rooms(orders)

    async def process_order_for_url(order):
        try:
            user = await retrieve_user_by_id(order.userID)
            if user and hasattr(order, 'panoramas'):
                builder = UrlBuilder(user.identity, order.itemID)
                for room in order.panoramas:
                    if room.isFirst:
                        url_picture = builder.get_img_url(ImageSize.size_150, room.filename)
                        return OrderWithPicture(**order.dict(), url_picture=url_picture)
            return OrderWithPicture(**order.dict(), url_picture=None)
        except Exception as e:
            log.error(f"Error for process order {order}: {e}")
            return OrderWithPicture(**order.dict(), url_picture=None)

    return list(await asyncio.gather(*[process_order_for_url(order) for order in new_orders]))


async def retrieve_orders_ids(limit: int, offset: int) -> list[PydanticObjectId]:
    log.debug("retrieve_orders_ids calling")

    query = Order.find_all().skip(offset).limit(limit).project(OrderId)
    return [order.id async for order in query]


async def retrieve_order_by_id(order_id: PydanticObjectId) -> Optional[Order]:
    log.debug("retrieve_order_by_id calling")

    return await Order.get(order_id)


async def retrieve_orders_by_user_id(
        user_id: PydanticObjectId, limit: int, offset: int
) -> list[Order]:
    log.debug("retrieve_orders_by_user_id calling")

    return await Order.find(Order.userID == user_id).skip(offset).limit(limit).to_list()


async def retrieve_orders_ids_by_user_id(
        user_id: PydanticObjectId, limit: int, offset: int
) -> list[PydanticObjectId]:
    log.debug("retrieve_orders_ids_by_user_id calling")

    query = (
        Order.find(Order.userID == user_id).skip(offset).limit(limit).project(OrderId)
    )
    return [order.id async for order in query]


async def retrieve_orders_count_by_user_id(user_id: PydanticObjectId) -> int:
    log.debug("retrieve_orders_count_by_user_id calling")
    return await Order.find(Order.userID == user_id).count()


async def create_order(name: str, userID: PydanticObjectId, created: datetime):
    # TODO: figure out real item creation procedure for correct order creation
    name_len = len(name)
    if name_len < 6:
        name_part = bytes(name, encoding="utf-8")
        user_part_len = 12 - name_len
        user_part = bytes(str(userID)[:user_part_len], encoding="utf-8")
    else:
        name_part = bytes(name[:6], encoding="utf-8")
        user_part = bytes(str(userID)[:6], encoding="utf-8")
    item_id = PydanticObjectId(name_part + user_part)
    new_order = Order(
        name=name,
        userID=userID,
        itemID=item_id,
        modified=created,
        createdByUser=created,
    )
    return await new_order.create()


async def retrieve_total_orders() -> int:
    log.debug("retrieve_total_orders_count calling")
    return await Order.find().count()


async def retrieve_all_orders() -> list[Order]:
    log.debug("retrieve_all_orders_count calling")
    return await Order.find_all().to_list()
