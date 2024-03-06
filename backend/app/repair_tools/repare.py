import logging
import asyncio
import json

from fastapi import APIRouter, HTTPException, Body
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from ..models.order import UpdateResponse, UpdateJSON
from ..models.damage import DamageLineItemList, DamageLineItem
from pydantic import ValidationError
from ..routers.order import repair_result_json

from ..s3.async_boto_wrapper import delete_objects
from ..s3.file_ops import rename_new_file_name, delete_json_file, sort_directory_list
from starlette.status import (
    HTTP_500_INTERNAL_SERVER_ERROR,
)
from ..s3.file_ops import (
    get_file_name_s3_folder,
    get_json_from_s3,
    write_json_file,
    update_json_file,
    delete_all_files_from_directories,
    delete_json_file,
    sort_directory_list,
    create_json_file
)

from ..config import settings

router = APIRouter(prefix="/repair", tags=["Repairs"])

logger = logging.getLogger(__name__)


def get_validate_line_item(line_item):
    try:
        if line_item is not None:
            validated_item = DamageLineItem(**line_item)
            return validated_item.right_dict

    except ValidationError:
        return None


async def repair_damage_json_id(file_path: str) -> None:
    try:
        data = await get_json_from_s3(
            s3_path=file_path
        )

        validation_results = [item for item in (get_validate_line_item(line_item) for line_item in data)
                              if item is not None]
        logger.info(validation_results)

        await write_json_file(
            srt_data=validation_results,
            s3_path=file_path
        )

        logger.success(f"Successfully update {file_path}")

    except Exception as e:
        logger.error(f"Failed for updated {file_path}: {e}")


def repair_damage_json_id_sync(file_path: str):
    asyncio.run(repair_damage_json_id(file_path))


@router.get(
    path="/repair_all_damage_json_id",
    summary="Repair id in damage file",
    response_model=UpdateResponse
)
async def repair_all_damage_json_id():
    logger.debug("The start of the REPAIR_ALL_DAMAGE_JSON_FILE route")

    try:
        all_file_name = await get_file_name_s3_folder(
            folder_path=""
        )

        exclusion_substring = '/storage/images/'
        exclusion_prefix = 'backup/'

        damage_file_name = [
            key for key in all_file_name if exclusion_substring
                                            not in key and not key.endswith('/')
                                            and not key.startswith(exclusion_prefix)
        ]

        with ThreadPoolExecutor(max_workers=3) as executor:
            executor.map(repair_damage_json_id_sync, damage_file_name)

        return UpdateResponse(message="Successfully updated id in all damage "
                                      "json files")
    except Exception as e:
        logger.error("An error occurred during the operation of the route "
                     f"UPDATE_ALL_LINE_ITEMS_JSON. DETAIL: {e}")

        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update AllLineitems.json"
        )


def convert_to_json_compatible(data):
    if isinstance(data, dict):
        for key, value in data.items():
            data[key] = convert_to_json_compatible(value)
    elif isinstance(data, list):
        data = [convert_to_json_compatible(item) for item in data]
    elif isinstance(data, bool):
        return str(data).lower()
    return data


def process_and_save_json(data):
    json_compatible_data = convert_to_json_compatible(data)

    return json.dumps(json_compatible_data)


def remove_duplicates_by_id(dicts):
    seen_ids = set()
    unique_dicts = []
    for d in dicts:
        if d['Id'] not in seen_ids:
            unique_dicts.append(d)
            seen_ids.add(d['Id'])
    return unique_dicts


@router.put(
    path="/repair_damage_path",
    summary="Repair path damage file in s3",
    response_model=UpdateResponse
)
async def repair_damage_path(
        old_path: Any = Body(None, embed=False),
        new_path: Any = Body(None, embed=False)
):
    logger.debug("The start of the REPAIR_DAMAGE_PATH route")

    try:
        await rename_new_file_name(old_path, new_path)

        return UpdateResponse(message="Successfully repair path damage file")
    except Exception as e:
        logger.error(f"An error occurred during the operation of the "
                     "REPAIR_DAMAGE_PATH. DETAIL: {e}")

        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to repair damage path. Detail: {e}"
        )
