import logging

from fastapi import APIRouter, HTTPException
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR

from ..crud.estimate import retrieve_estimate_with_pdfs
from ..models.estimate import EstimateOut


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/estimates", tags=["Estimates"])


@router.get("/", response_model=list[EstimateOut])
async def get_orders() -> list[EstimateOut]:
    logger.debug("The start of the GET_ORDE route")

    try:
        return await retrieve_estimate_with_pdfs()
    except Exception as e:
        logger.critical("An error occurred during the operation of the route"
                        "GET_ORDERS. DETAILS: {}".format(e))

        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,

        )