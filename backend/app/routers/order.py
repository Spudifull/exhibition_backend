import logging
import asyncio

from typing import Optional, Any, Union
from pydantic import ValidationError
from beanie import PydanticObjectId
from pydantic import HttpUrl
from fastapi import APIRouter, HTTPException, Query, UploadFile, Body
from starlette.status import (
    HTTP_201_CREATED,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
    HTTP_500_INTERNAL_SERVER_ERROR,
)

from ..crud.floorplan_order import retrieve_order_id_by_claim_number
from ..crud.order import (
    create_order,
    retrieve_order_by_id,
    retrieve_orders,
    retrieve_orders_by_user_id,
    retrieve_orders_count_by_user_id,
    retrieve_orders_ids,
    retrieve_orders_ids_by_user_id,
    retrieve_total_orders,
    get_url_picture_orders,
    retrieve_all_orders,
)

from ..crud.room import retrieve_order_rooms
from ..repair_tools.control_update import decorator_damage_log
from ..crud.user import retrieve_user_by_id
from ..external_apis.aime_api import read_estimate_post_call
from ..models.area import AiMeAPIResponse
from ..models.damage import DamageLineItem, DamageLineItemList
from ..models.order import (Order, OrderPost, PdfUploadResponse,
                            OrderResponse, UpdateResponse, UpdateJSON,
                            OrderResponseWithPicture,
                            JSONSubstitutionResponse,
                            DamageContentResponse,
                            UpdateResponseWithReport,
                            UpdateResponseWithURL
                            )
from ..models.user import User
from ..s3.file_ops import (create_json_file,
                           update_json_file,
                           delete_json_file,
                           write_json_file,
                           get_json_from_s3,
                           get_file_name_s3_folder,
                           delete_all_files_from_directories,
                           update_damage_file,
                           rename_new_file_name,
                           set_new_directory_name,
                           update_backup, copy_object_in_s3, reupdate_backup
                           )
from ..utils.url import UrlBuilder, check_url
from ..utils.process_areas import process_areas

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orders", tags=["Orders"])


async def get_order_and_user_by_id(
        order_id: PydanticObjectId,
) -> tuple[Optional[Order], Optional[User]]:
    logger.debug("The start of the GET_ORDER_AND_USER_BY_ID route")
    try:
        order = await retrieve_order_by_id(order_id)
        user = await retrieve_user_by_id(order.userID) if order else None

        return order, user
    except Exception as e:
        logger.error("An error occurred during the operation of the function"
                     "GET_ORDER_AND_USER_BY_ID. DETAILS: {}".format(e))

        raise


@router.get(
    path="/",
    response_model=OrderResponseWithPicture,
)
async def get_orders(
        limit: int = Query(20, gt=0),
        offset: int = Query(0, ge=0)
) -> OrderResponseWithPicture:
    try:
        logger.debug("The start of the GET_ORDERS route")

        orders = await retrieve_orders(limit, offset)
        orders = await get_url_picture_orders(orders)
        await update_orders_with_user_info(orders)
        total = await retrieve_total_orders()

        logger.success("The route GET_ORDERS has been successfully completed, "
                       "The request is being sent")
        return OrderResponseWithPicture(total_orders=total, orders=orders)
    except Exception as e:
        logger.critical("An error occurred during the operation of the route"
                        "GET_ORDERS. DETAILS: {}".format(e))
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=f"Error when receiving orders",
        )


@router.post(
    path="/",
    status_code=HTTP_201_CREATED,
    response_model=Order
)
async def post_order(order: OrderPost) -> Order:
    try:
        logger.debug("The start of the POST_ORDER route")

        order = await create_order(**order.model_dump(exclude={"id"}))

        logger.success("The route POST_ORDER has been successfully completed. "
                       "The request is being sent")
        return order
    except Exception as e:
        logger.critical("An error occurred during the operation of the route"
                        "POST_ORDER. DETAILS: {}".format(e))
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=f"Error when creating an order",
        )


@router.get(
    path="/ids",
    response_model=list[PydanticObjectId]
)
async def get_order_ids(
        limit: int = Query(20, gt=0),
        offset: int = Query(0, ge=0),
) -> list[PydanticObjectId]:
    try:
        logger.debug("The start of the GET_ORDER_IDS route")

        list_ids = await retrieve_orders_ids(limit=limit, offset=offset)

        logger.success("The route GET_ORDERS_IDS has been successfully completed. "
                       "The request is being sent")
        return list_ids
    except Exception as e:
        logger.critical("An error occurred during the operation of the route"
                        "GET_ORDER_IDS. DETAILS: {}".format(e))
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=f"Error when trying to receive an orders ids",
        )


@router.get(
    path="/{order_id}",
    response_model=Order,
    summary="Get Orders by Id"
)
async def get_order_by_id(
        order_id: PydanticObjectId
) -> Order:
    try:
        logger.debug("The start of the GET_ORDER_BY_ID route")

        order = await retrieve_order_by_id(order_id)

        if not order:
            logger.warning("Order has not been found with id %s",
                           str(order_id))

            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail=f"order with id: {order_id} not found"
            )

        user = await retrieve_user_by_id(order.userID)
        if user:
            await update_order_with_url(order, user)

        logger.success("The route GET_ORDERS_BY_ID has been successfully completed. "
                       "The request is being sent")

        return order
    except Exception as e:
        logger.critical("An error occurred during the operation of the route"
                        "GET_ORDER_BY_ID. DETAILS: {}".format(e))
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=f"Error when creating an order",
        )


@router.get(
    "/by_user_id/{user_id}",
    response_model=OrderResponseWithPicture,
    summary="Get Orders and and their number of a User Specified by Id",
)
async def get_orders_by_user_id(
        user_id: PydanticObjectId,
        limit: int = Query(20, gt=0),
        offset: int = Query(0, ge=0),
) -> OrderResponse:
    try:
        logger.debug("The start of the GET_ORDERS_BY_USER_ID route")

        orders = await retrieve_orders_by_user_id(user_id, limit, offset)

        if orders is None:
            logger.warning("Orders has not been found with user_id %s",
                           str(user_id))

            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail=f"Orders with this user_id does not"
            )

        orders = await get_url_picture_orders(orders)
        await update_orders_with_user_info(orders)

        logger.success("The route GET_ORDERS_BY_USERS_ID has been successfully completed. "
                       "The request is being sent")

        return OrderResponseWithPicture(total_orders=len(orders), orders=orders)
    except Exception as e:
        logger.critical("An error occurred during the operation of the route"
                        "GET_ORDERS_BY_USER_ID. DETAILS: {}".format(e))

        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=f"Error when creating an order",
        )


@router.get(
    path="/by_user_id/{user_id}/ids",
    response_model=list[PydanticObjectId]
)
async def get_orders_ids_by_user_id(
        user_id: PydanticObjectId,
        limit: int = Query(20, gt=0),
        offset: int = Query(0, ge=0),
) -> list[PydanticObjectId]:
    try:
        logger.debug("The start of the GET_ORDERS_IDS_BY_USER_ID route")

        list_order_ids = await retrieve_orders_ids_by_user_id(user_id, limit, offset)

        logger.success("The route GET_ORDERS_IDS_BY_USER_ID has been successfully completed. "
                       "The request is being sent")

        return list_order_ids
    except Exception as e:
        logger.critical("An error occurred during the operation of the route"
                        "GET_ORDERS_IDS_BY_USER_ID. DETAILS: {}".format(e))
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=f"Error when creating an order",
        )


@router.get("/by_user_id/{user_id}/count", response_model=int)
async def get_orders_count_by_user_id(
        user_id: PydanticObjectId,
) -> int:
    try:
        logger.debug("The start of the GET_ORDERS_COUNT_BY_USER_ID route")

        count_orders = await retrieve_orders_count_by_user_id(user_id)

        logger.success("The route GET_ORDERS_COUNT_BY_USER_ID has been "
                       "successfully completed. The request is being sent")

        return count_orders
    except Exception as e:
        logger.critical("An error occurred during the operation of the route "
                        "GET_ORDERS_COUNT_BY_USER_ID. DETAILS: {}".format(e))

        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=f"Error when count orders by this user_id"
        )


async def validate_file_type(content_type: str,
                             expected_content_type: str = "application/pdf") -> None:
    logger.debug("The start of the VALIDATE_FILE_TYPE function")

    if content_type != expected_content_type:
        logger.error("The function VALIDATE_FILE_TYPE has been error"
                     f"File content type must be {expected_content_type}")

        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=f"File content type must be {expected_content_type}",
        )


async def process_file(filename: str, content: bytes) -> AiMeAPIResponse:
    try:
        logger.debug("The start of the PROCESS_FILE function")

        api_result = await read_estimate_post_call(filename, content)

        logger.info(api_result)

        if api_result is None:
            logger.critical("The function PROCESS_FILE has been error"
                            "File came empty from external API")

            raise HTTPException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                detail="File came empty from external API",
            )

        return api_result
    except ValueError as e:
        logger.critical("An error occurred during the operation of the function "
                        "PROCESS_FILE. DETAILS: {}".format(e))

        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to call external API",
        )


async def get_order_builder_path(order_id: PydanticObjectId) -> UrlBuilder:
    logger.debug("The start of the GET_ORDER_BUILDER_PATH function")

    order, user = await get_order_and_user_by_id(order_id)

    match (order, user):
        case (None, _):
            logger.critical(f"The function GET_SINGLE_ORDER_IDS_BY_CLAIM_NUMBER has been error"
                            f"Order with id: {order_id} not found")

            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail=f"Order with id: {order_id} not found",
            )

        case (_, None):
            logger.critical(f"The function GET_SINGLE_ORDER_IDS_BY_CLAIM_NUMBER has been error"
                            f"User with id: {order.userID} not found")

            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail=f"User with id: {order.userID} not found",
            )

    builder = UrlBuilder(user.identity, order.itemID)

    return builder


async def process_room_and_generate_url(room_id, room_items, builder: UrlBuilder):
    logger.debug("The start of the PROCESS_ROOM_AND_GENERATE_URL function")

    try:
        s3_path = builder.get_s3_json_path(f"{room_id}.json")
        await create_json_file(room_items.model_dump(by_alias=True), s3_path)
        return builder.get_external_json_url(f"{room_id}.json")

    except Exception as e:
        logger.error("An error occurred during the operation of the function "
                     "PROCESS_ROOM_AND_GENERATE_URL. DETAILS: {}".format(e))

        raise


async def process_rooms_and_generate_urls(order_id: PydanticObjectId,
                                          api_result: AiMeAPIResponse, builder: UrlBuilder) -> list[HttpUrl]:
    try:
        rooms = await retrieve_order_rooms(order_id, url_check=False)
        rooms_with_areas = process_areas(api_result, rooms)

        tasks = [process_room_and_generate_url(room_id, room_items, builder) for room_id, room_items in
                 rooms_with_areas.items()]

        external_urls = await asyncio.gather(*tasks)

        return list(external_urls)

    except Exception as e:
        logger.error("An error occurred during the operation of the function "
                     "PROCESS_ROOMS_AND_GENERATE_URLS. DETAILS: {}".format(e))

        raise


async def get_single_order_ids_by_claim_number(claim_number: str) -> PydanticObjectId:
    logger.debug("The start of the GET_SINGLE_ORDER_IDS_BY_CLAIM_NUMBER route")

    order_ids = await retrieve_order_id_by_claim_number(claim_number)

    match order_ids:

        case []:
            logger.critical(f"The function GET_SINGLE_ORDER_IDS_BY_CLAIM_NUMBER has been error"
                            f"Failed to retrieve order_id for claim number: {claim_number}")

            raise HTTPException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve order_id for claim number: {claim_number}"
            )

        case [single_order_id]:
            logger.success("The function GET_SINGLE_ORDER_IDS_BY_CLAIM_NUMBER has been "
                           "successfully completed. The request is being sent")

            return single_order_id

        case _:
            logger.critical(f"The function GET_SINGLE_ORDER_IDS_BY_CLAIM_NUMBER has been error"
                            f"Multiple orders retrieved for claim number: {claim_number}")

            raise HTTPException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Multiple orders retrieved for claim number: {claim_number}"
            )


@router.post(
    "/upload_pdf", summary="Upload Estimate PDF", response_model=PdfUploadResponse
)
async def upload_pdf(file: UploadFile) -> PdfUploadResponse:
    """
    Uploads a PDF file and performs various operations on it.

    Args:
    - file (UploadFile): The PDF file to be uploaded.

    Returns:
    - PdfUploadResponse: The response containing information about the uploaded PDF file.

    Raises:
    - HTTPException: If the file content type is not 'application/pdf'.
    - HTTPException: If there is an error calling the external API.
    - HTTPException: If there is an error retrieving the order ID for the claim number.
    - HTTPException: If there are multiple orders retrieved for the claim number.
    - HTTPException: If the order or user with the specified ID is not found.

    Note:
    - This function assumes that the file content type is 'application/pdf'.
    - The order ID is retrieved using the claim number.
    - The order and user are retrieved using the order ID.
    - The JSON files are created and uploaded to an S3 bucket.
    - The external URLs of the JSON files are returned in the response.
    """

    logger.debug("The start of the UPLOAD_PDF route")

    await validate_file_type(file.content_type)
    file_content = await file.read()

    api_result = await process_file(file.filename, file_content)
    claim_number = api_result.Claim

    order_id = await get_single_order_ids_by_claim_number(claim_number=claim_number)
    builder = await get_order_builder_path(order_id=order_id)

    try:
        await create_json_file(api_result.model_dump(by_alias=True), builder.get_s3_json_path("result.json"))

        logger.success("The route UPLOAD_PDF has been successfully completed. "
                       "The request is being sent")

        return PdfUploadResponse(
            order_id=order_id,
            claim_number=claim_number,
            order_json_url=builder.get_external_json_url("result.json"),
            rooms_json_urls=await process_rooms_and_generate_urls(order_id, api_result, builder),
        )
    except Exception as e:
        logger.critical("An error occurred during the operation of the route"
                        "UPLOAD_PDF. DETAILS: {}".format(e))

        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error when creating jsons for pdf",
        )


@router.post(
    "/{order_id}/upload_pdf",
    summary="Upload Estimate PDF to Order",
    response_model=PdfUploadResponse,
)
async def upload_pdf_to_order(order_id: PydanticObjectId, file: UploadFile) -> PdfUploadResponse:
    """
    Uploads an Estimate PDF to an Order.

    Parameters:
    - order_id: The ID of the Order to upload the PDF to. (Type: PydanticObjectId)
    - file: The PDF file to upload. (Type: UploadFile)

    Returns:
    - A dictionary containing the API result JSON. (Type: dict)

    Raises:
    - HTTPException: If the file content type is not 'application/pdf'.
    - HTTPException: If the external API call fails.
    - HTTPException: If the order with the specified ID is not found.
    - HTTPException: If the user with the specified ID is not found.
    """
    logger.debug("The start of the UPLOAD_PDF_TO_ORDER route")

    await validate_file_type(file.content_type)
    file_content = await file.read()

    api_result = await process_file(file.filename, file_content)
    builder = await get_order_builder_path(order_id=order_id)

    try:
        logger.success("The route UPLOAD_PDF_TO_ORDER has been successfully completed. "
                       "The request is being sent")

        await create_json_file(api_result.model_dump(by_alias=True), builder.get_s3_json_path("result.json"))

        return PdfUploadResponse(
            order_id=order_id,
            claim_number=None,
            order_json_url=builder.get_external_json_url("result.json"),
            rooms_json_urls=await process_rooms_and_generate_urls(order_id, api_result, builder),
        )

    except Exception as e:
        logger.critical("An error occurred during the operation of the route"
                        "UPLOAD_PDF_TO_ORDER. DETAILS: {}".format(e))

        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error when creating jsons for pdf and order",
        )


def repair_result_json(updates_json: dict) -> dict:
    logger.debug("The start of the REPAIR_RESULT_JSON function")

    try:
        repair = AiMeAPIResponse.model_validate(updates_json)
        return repair.model_dump(by_alias=True)
    except Exception as e:
        logger.error(f"Error when repair file result.json: {e}")

        return updates_json


@router.put(
    path="/change_result_json/{order_id}",
    summary="Change result.json file",
    response_model=UpdateResponseWithURL,
)
async def change_result_json_file(order_id: PydanticObjectId,
                                  updates: UpdateJSON) -> UpdateResponseWithURL:
    """
        Change JSON Result file for Order.

        Parameters:
        - order_id: The ID of the Order to upload the JSON file. (Type: PydanticObjectId)
        - dict: The update dictionary for JSON file. (Type: str)

        Returns:
        - An UpdateResponse object with message confirming the completion of the operation. (Type: dict)

        Raises:
        - HTTPException: If the order with the specified ID is not found. (function: get_order_s3_path)
        - HTTPException: If the user with the specified ID is not found.  (function: get_order_s3_path)
        - HTTPException: If update file is failed.
    """
    logger.debug("The start of the CHANGE_RESULT_JSON_FILE function")

    try:
        new_updates = repair_result_json(updates_json=updates.updates)
        builder = await get_order_builder_path(order_id)
        update_response = await update_json_file(update_data=new_updates,
                                                 s3_path=builder.get_s3_json_path("result.json"))

        logger.success("The route CHANGE_RESULT_JSON_FILE has been successfully completed. "
                       "The request is being sent")

        return UpdateResponseWithURL(
            **update_response.dict(),
            json_url=builder.get_external_json_url("result.json")
        )

    except HTTPException as http_exc:

        if http_exc.status_code == HTTP_404_NOT_FOUND:

            raise http_exc

        else:

            logging.critical(f"An error occurred during the operation of the route CHANGE_RESULT_JSON_FILE. "
                             f"Failed to change object: {http_exc.detail}")

            raise HTTPException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to change result json file: {http_exc.detail}"
            )

    except Exception as e:
        logger.critical("An error occurred during the operation of the route"
                        "CHANGE_RESULT_JSON_FILE. DETAILS: {}".format(e))

        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Failed to update result.json file. Detail: {e}',
        )


@router.delete(
    path="/delete_result_json/{order_id}",
    summary="Delete result.json file",
    response_model=UpdateResponse,
)
async def delete_result_json_file(order_id: PydanticObjectId) -> UpdateResponse:
    """
            Delete JSON Result file for Order.

            Parameters:
            - order_id: The ID of the Order to upload the JSON file. (Type: PydanticObjectId)

            Returns:
            - An UpdateResponse object with message confirming the completion of the operation. (Type: dict)

            Raises:
            - HTTPException: If the order with the specified ID is not found. (function: get_order_s3_path)
            - HTTPException: If the user with the specified ID is not found.  (function: get_order_s3_path)
            - HTTPException: If delete file is failed.
    """
    logger.debug("The start of the DELETE_RESULT_JSON_FILE function")

    try:
        builder = await get_order_builder_path(order_id)
        delete_response = await delete_json_file(s3_path=builder.get_s3_json_path("result.json"))

        logger.success("The route DELETE_RESULT_JSON_FILE has been successfully completed. "
                       "The request is being sent")

        return delete_response

    except HTTPException as http_exc:

        if http_exc.status_code == HTTP_404_NOT_FOUND:

            raise http_exc

        else:

            logging.critical(f"An error occurred during the operation of the route DELETE_RESULT_JSON_FILE. "
                             f"Failed to delete object: {http_exc.detail}")

            raise HTTPException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete result json file: {http_exc.detail}"
            )

    except Exception as e:
        logger.critical("An error occurred during the operation of the route"
                        "DELETE_RESULT_JSON_FILE. DETAILS: {}".format(e))

        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete result.json file",
        )


async def update_order_with_url(order: Order, user: User):
    logger.debug("The start of the UPDATE_ORDER_WITH_URL function")

    try:
        builder = UrlBuilder(user.identity, order.itemID)
        url = builder.get_external_json_url("result.json")
        if await check_url(url.unicode_string()):
            order.lineItemJsonUrl = url

    except Exception as e:
        logger.critical("An error occurred during the operation of the function"
                        "UPDATE_ORDER_WITH_URL. DETAILS: {}".format(e))

        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,

            # You can make the error return more informative
            detail=f"Error updating the order {order.id}",
        )


async def update_orders_with_user_info(orders: list[Order]):
    logger.debug("The start of the UPDATE_ORDER_WITH_URL function")

    try:
        user_ids = {order.userID for order in orders}
        user_tasks = [retrieve_user_by_id(user_id) for user_id in user_ids]
        users = await asyncio.gather(*user_tasks)
        user_map = {user.id: user for user in users}

        update_tasks = [update_order_with_url(order, user_map.get(order.userID)) for order in orders]
        await asyncio.gather(*update_tasks)

    except Exception as e:
        logger.error("An error occurred during the operation of the function"
                     "UPDATE_ORDERS_WITH_USER_INFO. DETAILS: {}".format(e))

        raise


@router.put(
    path="/save_damage_json/",
    summary="Save damage result to file",
    response_model=UpdateResponse,
)
async def change_damage_json_file(
        damage_type: Any = Body(None, embed=False),
        data_json: Any = Body(None, embed=False),
        list_damage_json: Any = Body(None, embed=False),
        substitution_type: Any = Body(None, embed=False),
        substitution_json: JSONSubstitutionResponse = Body(None, embed=False)
) -> UpdateResponse:
    logger.debug("The start of the CHANGE_DAMAGE_JSON_FILE route")

    try:
        match (damage_type, data_json, list_damage_json,
               substitution_type, substitution_json):

            case (None, None, None, None, None):
                logger.critical("An error occurred during the operation of the route"
                                "CHANGE_DAMAGE_JSON_FILE. Invalid request parameters")

                raise HTTPException(
                    status_code=HTTP_400_BAD_REQUEST,
                    detail="Invalid request parameters"
                )

            case (_, _, None, None, None) | (_, None, None, _, _):

                if not damage_type:
                    logger.critical("An error occurred during the operation of the route"
                                    "CHANGE_DAMAGE_JSON_FILE. Damage_type is required")

                    raise HTTPException(
                        status_code=HTTP_400_BAD_REQUEST,
                        detail="damage_type is required"
                    )

                damage_type_normalized = damage_type.lower().replace(" ", "_")

                file_path = None

                match (data_json, substitution_json):
                    case (None, _):
                        file_name = (substitution_json.json_substitution_name.
                                     lower().replace(" ", "_"))
                        data_json = substitution_json.json_substitution_body

                        file_path = (
                            UrlBuilder.get_internal_json_url_for_substitution_file
                            (
                                damage_type_normalized,
                                file_name,
                                substitution_type
                            )
                        )
                    case (_, None):
                        file_path = (
                            UrlBuilder.get_internal_json_url_for_damage_file(
                                damage_type_normalized
                            )
                        )

                logger.info(file_path)

                return await write_json_file(srt_data=data_json, s3_path=file_path)

            case (None, None, _, None, None):
                return await update_json_file(update_data=list_damage_json, s3_path="damage_type.json")

            case _:
                logger.critical("An error occurred during the operation of the route"
                                " SAVE_DAMAGE_JSON. Invalid combination of request parameters")

                raise HTTPException(
                    status_code=HTTP_400_BAD_REQUEST,
                    detail="Invalid combination of request parameters"
                )
    except HTTPException as http_exc:

        if http_exc.status_code == HTTP_404_NOT_FOUND:

            raise http_exc

        else:

            logging.critical(f"An error occurred during the operation of the route DELETE_DAMAGE_JSON. "
                             f"Failed to update object: {http_exc.detail}")

            raise HTTPException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to change damage json file: {http_exc.detail}"
            )

    except Exception as e:
        logging.critical(f"An error occurred during the operation of the route"
                         f"SAVE_DAMAGE_JSON.Error in change_result_json_file: {e}")

        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update result.json file: {e}"
        )


@router.delete(
    path="/delete_damage_json/{type_damage}",
    summary="Delete damage file the selected type",
    response_model=UpdateResponse
)
async def delete_damage_json(
        type_damage: str,
        substitution_type: Optional[str] = None,
        substitution_file_name: Optional[str] = None,
):
    logger.debug("The start of the DELETE_DAMAGE_JSON route")

    try:
        match (type_damage, substitution_type,
               substitution_file_name):

            case (_, None, None):

                return await delete_all_files_from_directories(
                    folder_path=UrlBuilder.get_internal_damage_directory_url(
                        type_damage
                    )
                )

            case (_, _, _):

                return await delete_json_file(
                    s3_path=UrlBuilder.get_internal_json_url_for_substitution_file(
                        type_damage,
                        substitution_file_name,
                        substitution_type
                    )
                )

            case _:
                logger.critical("An error occurred during the operation of the route"
                                " DELETE_DAMAGE_JSON. Invalid combination of request parameters")

                raise HTTPException(
                    status_code=HTTP_400_BAD_REQUEST,
                    detail="Invalid combination of request parameters"
                )

    except HTTPException as http_exc:

        if (http_exc.status_code == HTTP_404_NOT_FOUND or
                http_exc.status_code == HTTP_400_BAD_REQUEST):

            raise http_exc

        else:

            logging.critical(f"An error occurred during the operation of the route DELETE_DAMAGE_JSON. "
                             f"Failed to update object: {http_exc.detail}")

            raise HTTPException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete file: {http_exc.detail}"
            )

    except Exception as e:
        logging.critical(f"An error occurred during the operation of the route DELETE_DAMAGE_JSON. "
                         f"Failed to update object: {e}")

        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete file: {e}"
        )


async def preparing_json_for_repair(order: Order) -> None:
    logger.debug("The start of the PREPARING_JSON_FOR_REPAIR function")

    try:
        builder = await get_order_builder_path(order.id)
        result_json = await get_json_from_s3(s3_path=builder.get_s3_json_path("result.json"))
        updates = UpdateJSON(updates=result_json)
        await change_result_json_file(order_id=order.id, updates=updates)

        return
    except HTTPException as http_exc:

        if http_exc.status_code == HTTP_404_NOT_FOUND:
            logger.info(f"File not found for path: "
                        f"{builder.get_s3_json_path('result.json')}")

        else:
            logger.error("An error occurred during the operation of the function"
                         f"PREPARING_JSON_FOR_REPAIR.HTTP error detail: {http_exc.detail}")

            raise

    except Exception as e:
        logger.error("An error occurred during the operation of the function"
                     f"PREPARING_JSON_FOR_REPAIR.Failed to repair result.json for order {order.id}: {e}")
        raise


@router.get(
    path="/repair_all_result_json/",
    summary="Repair result.json",
    response_model=UpdateResponse,
)
async def repair_all_result_json() -> UpdateResponse:
    try:
        all_orders = await retrieve_all_orders()

        tasks = [preparing_json_for_repair(order) for order in all_orders]

        await asyncio.gather(*tasks)

        logger.success("The route REPAIR_ALL_RESULT_JSON_ has been successfully completed. "
                       "The request is being sent")

        return UpdateResponse(message="Completed repairs on all result.json files")

    except Exception as e:
        logger.error("An error occurred during the operation of the route"
                     f"REPAIR_ALL_RESULT_JSON.Failed to repair result.json for order: {e}")

        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update repair all result.json. Detail: {e}"
        )


@router.get(
    path="/get_contents_damage_directory/{damage_type}",
    summary="The route returns the contents of the damage folder",
    response_model=DamageContentResponse,
)
async def get_contents_damage_directory(damage_type: str) -> DamageContentResponse:
    try:
        exclude_file_name = "{dir}/{dir}.json".format(dir=damage_type)
        files_names = await get_file_name_s3_folder(f"{damage_type}/")

        def get_category(file_path: str) -> Optional[str]:
            parts = file_path.split("/")

            def check_category(category: str) -> bool:
                return category in parts

            match True:
                case _ if check_category("subtype"):
                    return "subtype"
                case _ if check_category("group"):
                    return "group"
                case _:
                    return None

        list_url_substitution_file = {
            category: [
                UrlBuilder.get_external_json_url_for_damage_file(file_name)
                for file_name in files_names if get_category(file_name) == category
            ]
            for category in set(map(get_category, files_names)) if category
        }

        # list_url_substitution_file = [
        # UrlBuilder.get_external_json_url_for_damage_file(file_name)
        # for file_name in files_names
        # if file_name != exclude_file_name and file_name != f"{damage_type}/"
        # ]

        return DamageContentResponse(
            name_damage=damage_type,
            url_damage_file=UrlBuilder.get_external_json_url_for_damage_file(exclude_file_name),
            url_substitution_file=list_url_substitution_file
        )

    except HTTPException as http_exc:

        if http_exc.status_code == HTTP_404_NOT_FOUND:

            raise http_exc

        else:

            logging.critical(f"An error occurred during the operation of the route GET_CONTENTS_DAMAGE_DIRECTORY. "
                             f"Failed to receive damage folder: {http_exc.detail}")

            raise HTTPException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to receive damage folder: {http_exc.detail}"
            )

    except Exception as e:
        logger.error("An error occurred during the operation of the route "
                     f"GET_CONTENTS_DAMAGE_DIRECTORY. DETAIL: {e}")

        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to receive the contents of the damage folder"
        )


@router.put(
    path="/update_damage_file/",
    summary="The route returns the contents of the damage folder",
    response_model=UpdateResponseWithReport,
)
@decorator_damage_log
async def update_damage_json(
        damage_type: Any = Body(None, embed=False),
        data_json: Any = Body(None, embed=False),
        list_damage_json: Any = Body(None, embed=False),
        substitution_type: Any = Body(None, embed=False),
        substitution_json: JSONSubstitutionResponse = Body(None, embed=False)
) -> UpdateResponseWithReport:
    logger.debug("The start of the UPDATE_DAMAGE_FILE route")

    try:
        match (damage_type, data_json, substitution_json, list_damage_json):
            case (None, None, None, None):

                logger.critical("An error occurred: At least one of 'damage_type' or 'list_damage_json' is required")

                raise HTTPException(
                    status_code=HTTP_400_BAD_REQUEST,
                    detail="At least one of 'damage_type' or 'list_damage_json' is required"
                )

            case (_, None, _, None) | (_, _, None, None):
                if not damage_type:
                    logger.critical("An error occurred during the operation of the route"
                                    "UPDATE_DAMAGE_FILE. Damage_type is required")
                    raise HTTPException(
                        status_code=HTTP_400_BAD_REQUEST,
                        detail="damage_type is required"
                    )

                match (data_json, substitution_json):
                    case (_, None):
                        validation_items = DamageLineItemList(data_json)

                        validation_list = validation_items.get_validation_result()

                        await update_damage_file(
                            damage_type=damage_type,
                            new_data=validation_list["valid_items"]
                        )

                        return UpdateResponseWithReport(
                            message="Updated successfully damage file",
                            validation_errors=validation_list["invalid_items"]
                        )

                    case (None, _):
                        file_name = (substitution_json.json_substitution_name.
                                     lower().replace(" ", "_"))
                        data_json = substitution_json.json_substitution_body

                        file_path = (
                            UrlBuilder.get_internal_json_url_for_substitution_file
                            (
                                damage_type,
                                file_name,
                                substitution_type
                            )
                        )

                        validation_items = DamageLineItemList(data_json)

                        validation_list = validation_items.get_validation_result()

                        await update_json_file(
                            update_data=validation_list["valid_items"],
                            s3_path=file_path
                        )

                        return UpdateResponseWithReport(
                            message="Updated successfully damage file",
                            validation_errors=validation_list["invalid_items"]
                        )

            case (None, None, None, _):

                await update_json_file(
                    update_data=data_json,
                    s3_path="damage_type.json"
                )

                return UpdateResponseWithReport(
                    message="Updated successfully damage_type file"
                )

            case _:
                logger.critical("An error occurred during the operation of the route"
                                " UPDATE_DAMAGE_FILE. Invalid combination of request parameters")

                raise HTTPException(
                    status_code=HTTP_400_BAD_REQUEST,
                    detail="Invalid combination of request parameters"
                )

    except HTTPException as http_exc:

        if (http_exc.status_code == HTTP_404_NOT_FOUND or
                http_exc.status_code == HTTP_400_BAD_REQUEST):

            raise http_exc

        else:

            logging.critical(f"An error occurred during the operation of the route GET_CONTENTS_DAMAGE_DIRECTORY. "
                             f"Failed to receive damage folder: {http_exc.detail}")

            raise HTTPException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update damage json: {http_exc.detail}"
            )

    except Exception as e:
        logger.error("An error occurred during the operation of the route "
                     f"UPDATE_DAMAGE_FILE. DETAIL: {e}")

        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update damage file. DETAIL: {e}"
        )


@router.put(
    path="/update_name_damage_file",
    summary="The route returns the contents of the damage folder",
    response_model=UpdateResponse,
)
async def update_name_damage_file(
        damage_type: Any = Body(None, embed=False),
        new_damage_type: Any = Body(None, embed=False),
        substitution_type: Any = Body(None, embed=False),
        old_substitution_name: Any = Body(None, embed=False),
        new_substitution_name: Any = Body(None, embed=False)
):
    try:
        match (damage_type, new_damage_type, substitution_type,
               old_substitution_name, new_substitution_name):
            case (_, _, None, None, None) | (_, None, _, _, _):

                old_path = new_path = ""
                match (new_damage_type, new_substitution_name,
                       substitution_type, old_substitution_name):
                    case (_, None, None, None):
                        await set_new_directory_name(
                            damage_type,
                            new_damage_type
                        )

                        old_path = (UrlBuilder.get_internal_other_damage_filename(
                            new_damage_type,
                            damage_type
                        )
                        )

                        new_path = UrlBuilder.get_internal_json_url_for_damage_file(
                            new_damage_type
                        )

                    case (None, _, _, _):
                        old_path = (
                            UrlBuilder.get_internal_json_url_for_substitution_file(
                                damage_type,
                                old_substitution_name,
                                substitution_type
                            )
                        )
                        new_path = (
                            UrlBuilder.get_internal_json_url_for_substitution_file(
                                damage_type,
                                new_substitution_name,
                                substitution_type
                            )
                        )
                        logger.info(f"new_path: {new_path}")
                await rename_new_file_name(old_path, new_path)

            case _:
                logger.critical("An error occurred during the operation of the route"
                                " UPDATE_DAMAGE_FILE. Invalid combination of request parameters")

                raise HTTPException(
                    status_code=HTTP_400_BAD_REQUEST,
                    detail="Invalid combination of request parameters"
                )

        return UpdateResponse(message="Successfully updated name damage_file")
    except HTTPException as http_exc:

        if (http_exc.status_code == HTTP_404_NOT_FOUND or
                http_exc.status_code == HTTP_400_BAD_REQUEST):

            raise http_exc

        else:

            logging.critical(f"An error occurred during the operation of the route GET_UPDATES_DAMAGE_DIRECTORY. "
                             f"Failed to receive name damage folder: {http_exc.detail}")

            raise HTTPException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update damage json: {http_exc.detail}"
            )

    except Exception as e:
        logger.error("An error occurred during the operation of the route "
                     f"UPDATE_NAME_DAMAGE_FILE. DETAIL: {e}")

        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update name damage file"
        )


def try_validate(line_item, index):
    try:
        validated_item = DamageLineItem(**line_item)
        return validated_item.right_dict, None

    except ValidationError as e:
        return None, (index, e.json())


@router.put(
    path="/set_all_line_items",
    summary="The route update json file AllLineitems",
    response_model=UpdateResponse
)
async def set_all_line_items_json(
        update_data: Any = Body(None, embed=False),
):
    logger.debug("The start of the SET_ALL_LINE_ITEMS route")

    validation_results = [try_validate(line_item, index) for index, line_item in enumerate(update_data)]
    errors = [error for item, error in validation_results if error is not None]

    if errors:
        logger.error(f"Invalid validation")

        error_details = ", ".join([f"index {index}: {error}" for index, error in errors])
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=f"Invalid validation for line_items: {error_details}"
        )

    try:
        update_data = [line_item for line_item, _ in validation_results]
        await write_json_file(srt_data=update_data,
                              s3_path="TrainAllLineItems.json")

        return UpdateResponse(message="Successfully updated AllLineitems.json")
    except Exception as e:
        logger.error("An error occurred during the operation of the route "
                     f"SET_ALL_LINE_ITEMS. DETAIL: {e}")

        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update AllLineitems.json"
        )


def get_validate_line_item(line_item):
    try:
        if line_item is not None:
            validated_item = DamageLineItem(**line_item)
            return validated_item.right_dict

    except ValidationError as e:
        logger.error(f"GET_VALIDATE_LINE_ITEMS. DETAIL: {e}")
        return None


def get_unique_line_item(list1: list, list2: list) -> list:
    unique_objects = {}

    for obj in list1 + list2:
        unique_objects[obj['Id']] = obj

    return list(unique_objects.values())


@router.put(
    path="/update_all_line_items_json",
    summary="Update file ALLLineItems.json",
    response_model=UpdateResponseWithReport
)
async def update_all_line_items_json(
        update_data: Any = Body(None, embed=False),
) -> UpdateResponseWithReport:
    logger.debug("The start of the UPDATE_ALL_LINE_ITEMS route")

    try:
        await copy_object_in_s3("TrainAllLineItems.json",
                                "temporary_backup/TrainAllLineItems.json")

        validation_items = DamageLineItemList(update_data)

        validation_list = validation_items.get_validation_result()

        old_data = await get_json_from_s3(
            s3_path="TrainAllLineItems.json"
        )

        result_list = get_unique_line_item(old_data,
                                           validation_list["valid_items"])

        await write_json_file(
            srt_data=result_list,
            s3_path="TrainAllLineItems.json"
        )

        return UpdateResponseWithReport(
            message="Successfully updated AllLineItems.json",
            validation_errors=validation_list["invalid_items"]
        )

    except HTTPException as http_exc:

        if (http_exc.status_code == HTTP_404_NOT_FOUND or
                http_exc.status_code == HTTP_400_BAD_REQUEST):

            raise http_exc

        else:

            logging.critical(f"An error occurred during the operation of the route GET_CONTENTS_DAMAGE_DIRECTORY. "
                             f"Failed to receive damage folder: {http_exc.detail}")

            raise HTTPException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update damage json: {http_exc.detail}"
            )

    except Exception as e:
        logger.error("An error occurred during the operation of the route "
                     f"UPDATE_ALL_LINE_ITEMS_JSON. DETAIL: {e}")

        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update AllLineitems.json"
        )


@router.get(
    path="/canceling_changes/",
    summary="When uploading new data to the damage file, we make a backup",
    response_model=UpdateResponse
)
async def canceling_changes() -> UpdateResponse:
    logger.debug("The start of the CANCELING_CHANGES route")

    try:
        await reupdate_backup()

        return UpdateResponse(
            message="Successful file rollback"
        )
    except HTTPException as http_exc:

        if (http_exc.status_code == HTTP_404_NOT_FOUND or
                http_exc.status_code == HTTP_400_BAD_REQUEST):

            raise http_exc

        else:

            logging.critical(f"An error occurred during the operation of the route GET_CONTENTS_DAMAGE_DIRECTORY. "
                             f"Failed to receive damage folder: {http_exc.detail}")

            raise HTTPException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update damage json: {http_exc.detail}"
            )

    except Exception as e:
        logger.error("An error occurred during the operation of the route "
                     f"CANCELING_CHANGES. DETAIL: {e}")

        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unsuccessful file rollback. DETAIL: {e}"
        )
