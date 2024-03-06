import logging

from beanie import PydanticObjectId

from ..models.floorplan_order import FloorplanOrder

logger = logging.getLogger(__name__)


async def retrieve_order_id_by_claim_number(
    claim_number: str,
) -> list[PydanticObjectId]:
    logger.debug("retrieve_order_id_by_claim_number calling")

    try:
        int_claim_number = int(claim_number)
    except ValueError:
        logger.error(f"Failed to parse claim number {claim_number}")
        return []

    fpos = FloorplanOrder.find(FloorplanOrder.internalOrderId == int_claim_number)
    return [fpo.virtualTourId async for fpo in fpos]
