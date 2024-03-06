import asyncio
import json
import logging
from datetime import datetime
from json import dumps
from typing import Union

from ..config import settings
from .async_boto_wrapper import (put_object, get_object, delete_object,
                                 executor, list_objects, delete_objects,
                                 copy_object, directory_object)
from ..models.order import UpdateResponse
from fastapi import HTTPException
from starlette.status import (
    HTTP_404_NOT_FOUND
)
from botocore.exceptions import ClientError
from ..utils.url import UrlBuilder
from ..models.damage import DamageLineItem
from pydantic import ValidationError

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


async def copy_object_in_s3(src_key, dest_key):
    try:
        copy_source = {
            'Bucket': settings.s3_bucket_name,
            'Key': src_key
        }

        log.info(f'Copying {src_key} to {dest_key}')

        await copy_object(
            CopySource=copy_source,
            Bucket=settings.s3_bucket_name,
            Key=dest_key
        )

        return UpdateResponse(message="Successfully copied")
    except ClientError as e:
        print(f"Failed to copy {src_key} to {dest_key}: {e}")


async def sort_directory_list():
    response = await directory_object(
        Bucket=settings.s3_bucket_name,
        Prefix="backup/",
        Delimiter="/"
    )

    folders = [content['Prefix'] for content in response.get('CommonPrefixes', [])]
    folders.sort()
    return folders


async def back_up_damage_file(
        dest_folder: str,
        daily_backup: bool = True
):
    try:
        all_file_name = await get_file_name_s3_folder(
            folder_path=""
        )

        exclusion_substring = '/storage/images/'
        exclusion_prefix = 'backup/'
        daily_exclusion_prefix = 'temporary_backup/'

        damage_file_name_gen = [
            key for key in all_file_name
            if exclusion_substring not in key
            and not key.endswith('/')
            and not key.startswith(exclusion_prefix)
            and not key.startswith(daily_exclusion_prefix)
        ]

        sort_list_directory = await sort_directory_list()

        if len(sort_list_directory) >= 7 and daily_backup:
            await delete_all_files_from_directories(sort_list_directory[0])

        tasks = [copy_object_in_s3(src_key, f"{dest_folder}{src_key}") for src_key in
                 damage_file_name_gen]

        await asyncio.gather(*tasks)

        return UpdateResponse(message="Successfully copied")
    except Exception as e:
        log.error(f"Error when attempt to backup file: {e}")
        raise


async def update_backup(destination: str):
    return await back_up_damage_file(
        dest_folder=destination,
        daily_backup=False
    )


async def reupdate_backup():
    try:
        all_file_name = await get_file_name_s3_folder(
            folder_path="temporary_backup/"
        )

        tasks = [copy_object_in_s3(src_key, src_key[len("temporary_backup/"):]) for src_key in
                 all_file_name]

        await asyncio.gather(*tasks)

        return UpdateResponse(message="Successfully copied")

    except Exception as e:
        log.error(f"Error when attempt to backup file: {e}")
        raise


async def daily_backup_file():
    backup_folder = datetime.now().strftime("backup/%d%m%Y/")
    return await back_up_damage_file(
        dest_folder=backup_folder
    )


async def set_new_file_name(old_name: str, new_name: str):
    try:
        copy_source = {
            "Bucket": settings.s3_bucket_name,
            "Key": old_name
        }

        await copy_object(
            Bucket=settings.s3_bucket_name,
            CopySource=copy_source,
            Key=new_name
        )

        return UpdateResponse(message="Files name updated successfully")
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchKey':
            log.error(f"File not found in S3 for this key")

            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail=f"File not found"
            )

        else:
            log.error(f"Error when get file from S3: {e}")
            raise


async def set_new_directory_name(old_prefix: str, new_prefix: str,
                                 is_copy: bool = False):
    log.info("set_new_directory_name call")

    try:
        file_names = await get_file_name_s3_folder(f"{old_prefix}/")
        tasks = []

        for file_name in file_names:
            task = asyncio.create_task(function_task_update_name(
                file_name, old_prefix, new_prefix, is_copy))
            tasks.append(task)

        await asyncio.gather(*tasks)

    except Exception as e:
        log.error(f"Error when update file name: {e}")
        raise


async def function_task_update_name(file_name: str, old_prefix: str, new_prefix: str, is_copy: bool):
    new_file_name = file_name.replace(old_prefix, new_prefix, 1)
    await set_new_file_name(file_name, new_file_name)

    if not is_copy:
        await delete_json_file(file_name)


async def rename_new_file_name(old_path: str, new_path: str) -> UpdateResponse:
    log.info(f"set_rename_file_name call")

    try:

        await set_new_file_name(
            old_path,
            new_path
        )

        await delete_json_file(
            old_path
        )

        return UpdateResponse(message="Files name updated successfully")
    except Exception as e:
        log.error(f"Error when update file name: {e}")
        raise


async def get_file_name_s3_folder(folder_path: str) -> list[str]:
    log.info(f"get_file_name_s3_folder call")

    files = await list_objects(
        Bucket=settings.s3_bucket_name,
        Prefix=folder_path
    )

    if not files:
        log.critical(f"")

        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail=f"Directory not found"
        )

    files_names = [file["Key"] for file in files]

    return files_names


async def update_all_files_from_damage_directories(damage_type: str,
                                                   difference: list):
    log.info(f"update_all_files_from_damage_directories call")

    try:
        list_file = await get_file_name_s3_folder(
            UrlBuilder.get_internal_damage_directory_url(damage_type)
        )

        list_file.remove(
            UrlBuilder.get_internal_json_url_for_damage_file(damage_type)
        )

        async def update_file_content(file_path: str) -> None:

            content = await get_json_from_s3(
                s3_path=file_path
            )

            updated_data = [item for item in content if item["Id"] not in difference]

            await write_json_file(updated_data, file_path)

        update_tasks = [update_file_content(path_file) for path_file in list_file]
        await asyncio.gather(*update_tasks)

        return UpdateResponse(message="Files updated successfully")
    except Exception as e:
        log.error(f"Error when update subtype files is s3: {e}")
        raise


def validate_line_item_in_new_file(line_item):
    try:
        if line_item is not None:
            validated_item = DamageLineItem(**line_item)
            return validated_item.right_dict

    except ValidationError as e:
        log.error(f"GET_VALIDATE_LINE_ITEMS. DETAIL: {e}")
        return None


async def update_damage_file(damage_type: str, new_data: list):
    log.info(f"update_damage_file call")

    try:
        s3_path = UrlBuilder.get_internal_json_url_for_damage_file(damage_type)

        await update_backup("temporary_backup/")

        old_data = await get_json_from_s3(
            s3_path
        )

        def find_difference(list_one: list, list_two: list) -> list:
            key_set_old = {item["Id"] for item in list_two}

            return [item["Id"] for item in list_one if item["Id"] not in key_set_old]

        difference = find_difference(old_data, new_data)

        if difference:
            await update_all_files_from_damage_directories(
                damage_type=damage_type,
                difference=difference
            )

        await write_json_file(new_data, s3_path)

        return UpdateResponse(message="File updated successfully")

    except Exception as e:
        if "404: File not found" in str(e):
            try:
                s3_path = UrlBuilder.get_internal_json_url_for_damage_file(damage_type)

                await write_json_file(
                    srt_data=new_data,
                    s3_path=s3_path
                )

                log.info(f"Create {s3_path} object from {settings.s3_bucket_name} bucket")

                return UpdateResponse(message="File updated successfully")
            except Exception as e:
                log.error(f"Error when create file from S3: {e}")
                raise
        else:
            log.error(f"Error when update file from S3: {e}")
            raise


async def delete_all_files_from_directories(folder_path: str) -> UpdateResponse:
    log.info(f"delete_all_files_from_directories call")

    try:
        list_file = await get_file_name_s3_folder(folder_path)

        delete_structure = {'Objects': [{'Key': file_name}
                                        for file_name in list_file],
                            'Quiet': False}

        await delete_objects(
            Bucket=settings.s3_bucket_name,
            Delete=delete_structure
        )

        return UpdateResponse(message="File deleted successfully")
    except Exception as e:
        log.error(f"Error when delete files is s3: {e}")
        raise


async def create_json_file(json_dict: dict, s3_path: str) -> None:
    log.info(f"Writing {s3_path} object to {settings.s3_bucket_name} bucket")

    try:

        await put_object(
            Bucket=settings.s3_bucket_name,
            Key=s3_path,
            Body=dumps(json_dict),
        )

    except Exception as e:
        log.error(f"Error when create files is s3: {e}")


async def check_file_exists_in_s3(s3_path: str) -> bool:
    try:
        await get_object(
            Bucket=settings.s3_bucket_name,
            Key=s3_path
        )
        return True

    except Exception as e:
        log.error(f"Error when checking file existence in S3: {e}")
        return False


async def get_json_from_s3(s3_path: str) -> Union[dict, list]:
    try:
        response = await get_object(
            Bucket=settings.s3_bucket_name,
            Key=s3_path
        )

        loop = asyncio.get_running_loop()
        json_content = await loop.run_in_executor(executor, response['Body'].read)
        return json.loads(json_content)

    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchKey':
            log.error(f"File not found in S3 for key: {s3_path}")

            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail=f"File not found"
            )

        else:
            log.error(f"Error when fetching file from S3: {e}")


async def write_json_file(srt_data: Union[str, list], s3_path: str) -> UpdateResponse:
    try:
        log.info(f"Writing {s3_path} object in {settings.s3_bucket_name} bucket")

        await put_object(
            Bucket=settings.s3_bucket_name,
            Key=s3_path,
            Body=json.dumps(srt_data)
        )

        return UpdateResponse(message="File updated successfully")
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchKey':
            log.error(f"File not found in S3 for key: {s3_path}")

            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail=f"File not found"
            )

        else:
            log.error(f"Error when updating file in S3: {e}")
            raise


def get_unique_line_item(list1: list, list2: list) -> list:
    unique_objects = {}

    for obj in list1 + list2:
        unique_objects[obj['Id']] = obj

    return list(unique_objects.values())


async def update_json_file(update_data: Union[dict, list], s3_path: str) -> UpdateResponse:
    log.info(f"Update_json_file call")

    try:
        current_content = await get_json_from_s3(s3_path)

        match update_data:
            case dict():
                updated_content = {**current_content, **update_data}
            case list():
                await copy_object_in_s3(
                    s3_path, f"temporary_backup/{s3_path}"
                )

                updated_content = get_unique_line_item(current_content,
                                                       update_data)
            case _:
                log.error("Unsupported type for update_data. It must be either dict or list.")
                raise ValueError("update_data must be either dict or list.")

        log.info(f"Update {s3_path} object from {settings.s3_bucket_name} bucket")

        await put_object(
            Bucket=settings.s3_bucket_name,
            Key=s3_path,
            Body=json.dumps(updated_content)
        )

        return UpdateResponse(message="File updated successfully")
    except Exception as e:
        if "404: File not found" in str(e):
            try:
                await write_json_file(
                    srt_data=update_data,
                    s3_path=s3_path
                )

                log.info(f"Create {s3_path} object from {settings.s3_bucket_name} bucket")

                return UpdateResponse(message="File written successfully")
            except Exception as e:
                raise
        else:

            log.error(f"Error when update file from S3: {e}")
            raise


async def delete_json_file(s3_path: str) -> UpdateResponse:
    try:
        log.info(f"Delete {s3_path} object from {settings.s3_bucket_name} bucket")

        await delete_object(
            Bucket=settings.s3_bucket_name,
            Key=s3_path
        )

        return UpdateResponse(message="File deleted successfully")
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchKey':
            log.error(f"File not found in S3 for key: {s3_path}")

            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail=f"File not found"
            )
        else:

            # Not sure if it's necessary, but for now, I'll leave the error output in this form.
            log.error(f"Error when delete file from S3: {e}")
            raise
