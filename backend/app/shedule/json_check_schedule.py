import asyncio
import logging
import aiohttp

from beanie import PydanticObjectId
from fastapi.exceptions import HTTPException
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR

from ..external_apis.aime_api import read_estimate_post_call
from ..models.area import AiMeAPIResponse
from ..models.estimate import Estimate
from ..models.floorplan_order import FloorplanOrder
from ..crud.order import retrieve_order_by_id
from ..crud.user import retrieve_user_by_id
from ..s3.file_ops import create_json_file, check_file_exists_in_s3
from ..utils.url import UrlBuilder

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


async def get_pdf_files_with_floor_plan_order_id(offset: int,
                                                 limit: int = 10) -> list[tuple[PydanticObjectId, str]]:
    pipeline = [
        {"$unwind": "$iterations"},
        {"$match": {
            "iterations.pdfFile": {"$exists": True, "$nin": [None, ""]}
        }},
        {"$project": {
            "_id": 0,
            "pdfFile": "$iterations.pdfFile",
            "floorplanOrderId": 1
        }},
        {"$group": {
            "_id": "$floorplanOrderId",
            "pdfFiles": {"$push": "$pdfFile"}
        }},
        {"$skip": offset},
        {"$limit": limit},
        {"$project": {
            "_id": 0,
            "result": {
                "$map": {
                    "input": "$pdfFiles",
                    "as": "pdf",
                    "in": {"floorplanOrderId": "$_id", "pdfFile": "$$pdf"}
                }
            }
        }}
    ]

    result = await Estimate.aggregate(pipeline).to_list()
    return [(item['floorplanOrderId'], item['pdfFile']) for group in result for item in
            group['result']] if result else []


async def get_floorplan_to_estimate_fpo(estimate_fpo: PydanticObjectId):
    floorplan_order = await FloorplanOrder.find_one(FloorplanOrder.id == estimate_fpo)
    return floorplan_order.virtualTourId if floorplan_order and hasattr(floorplan_order, 'virtualTourId') else None


async def retrieve_valid_orders(fpo_results_with_pdf):
    tasks = [(retrieve_order_by_id(fpo_id), pdfFile) for fpo_id, pdfFile in fpo_results_with_pdf]
    orders_with_exceptions = await asyncio.gather(*[task for task, _ in tasks], return_exceptions=True)

    user_tasks = [retrieve_user_by_id(order.userID) for order in orders_with_exceptions if
                  order is not None and not isinstance(order, Exception)]
    users = await asyncio.gather(*user_tasks)

    valid_orders_with_pdf = []
    for order, user, (_, pdfFile) in zip(orders_with_exceptions, users, tasks):
        if order is not None and not isinstance(order, Exception) and user is not None:
            valid_orders_with_pdf.append(({"itemID": order.itemID, "user_identity": user.identity}, pdfFile))
            if len(valid_orders_with_pdf) >= 10:
                break

    return valid_orders_with_pdf


async def process_file(filename: str, content: bytes) -> AiMeAPIResponse:
    try:
        api_result = await read_estimate_post_call(filename, content)

        if api_result is None:
            raise HTTPException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                detail="File came empty from external API",
            )
        return api_result
    except ValueError:
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to call external API",
        )


async def download_pdf(url: str) -> bytes:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                return await response.read()
            else:
                raise HTTPException(
                    status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to download PDF from {url}"
                )


async def process_pdf_file(pdf_url: str) -> AiMeAPIResponse:
    try:
        filename = pdf_url.split('/')[-1]

        pdf_content = await download_pdf(pdf_url)
        log.info(f"pdf_content: {len(pdf_content)}")

        api_result = await process_file(filename, pdf_content)
        return api_result
    except Exception as e:
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing PDF file: {e}"
        )


async def process_orders_and_create_jsons(valid_orders, counter: int) -> int:
    for order, pdfFile in valid_orders:
        if counter >= 10:
            break

        builder = UrlBuilder(order["user_identity"], order["itemID"])
        s3_json_path = builder.get_s3_json_path("result.json")

        log.info(f"Checking for an order with an ItemId: {order['itemID']}")
        success = await check_file_exists_in_s3(s3_json_path)

        if success:
            log.info(f"For order {order['itemID']} already has json")
            continue
        else:
            try:
                log.info(f"Starting to create a json file for the order: {order['itemID']}")
                api_result = await process_pdf_file(pdfFile)
                await create_json_file(api_result.model_dump(by_alias=True), s3_json_path)
                counter += 1
                log.info(f"Json uploaded successfully")
            except HTTPException as e:
                log.error(f"Error processing PDF for order {order['itemID']}: {e.detail}")

    return counter


async def get_fpo_list_with_pdf(offset: int, limit: int = 10) -> None:
    log.info("Task json_check_schedule start")
    counter = 0
    while counter < 10:
        estimates_pdf = await get_pdf_files_with_floor_plan_order_id(offset, limit)

        if not estimates_pdf:
            log.info("No more new estimates to process.")
            break

        tasks_with_pdf = [(get_floorplan_to_estimate_fpo(estimate_fpo), pdfFile)
                          for estimate_fpo, pdfFile in estimates_pdf]
        fpo_results_with_pdf = await asyncio.gather(*[task for task, _ in tasks_with_pdf])
        fpo_results = [(result, pdfFile) for result, (_, pdfFile) in
                       zip(fpo_results_with_pdf, tasks_with_pdf) if result is not None]

        valid_orders = await retrieve_valid_orders(fpo_results)

        item_ids = ", ".join(str(order["itemID"]) for order, _ in valid_orders)
        log.info(f"Find {len(valid_orders)} Valid Orders: {item_ids}")

        counter = await process_orders_and_create_jsons(valid_orders, counter)

        offset += limit

    log.info(f"Completed processing with counter: {counter}")
