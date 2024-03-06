import logging
import asyncio

from typing import Optional

from ..models.estimate import Estimate, EstimateOut
from ..models.floorplan_order import FloorplanOrder
from .order import retrieve_order_by_id

logger = logging.getLogger(__name__)


async def retrieve_estimate_with_pdfs() -> list[EstimateOut]:
    logger.debug("retrieve_estimate_with_pdfs calling")
    estimates = await Estimate.find_all().skip(22800).to_list()
    tasks = [process_estimate(e) for e in estimates]
    processed_estimates = await asyncio.gather(*tasks)
    return [estimate for estimate in processed_estimates if estimate is not None]


async def process_estimate(e) -> Optional[EstimateOut]:
    logger.debug("process_estimate calling")

    fpo = await FloorplanOrder.get(e.floorplanOrderId)
    match fpo:
        case None | object() if fpo.virtualTourId is None:
            return None

    order = await retrieve_order_by_id(fpo.virtualTourId)
    match order:
        case None:
            return None

    pdfs = [it.pdfFile for it in e.iterations if it.pdfFile]
    match pdfs:
        case []:
            return None

    return EstimateOut(
        estimate_id=e.id,
        tour_id=order.id,
        pdfs=pdfs,
        fpo_internalOrderId=fpo.internalOrderId,
    )
