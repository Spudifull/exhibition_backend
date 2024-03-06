import asyncio
from datetime import datetime
from ..config import settings
from typing import Callable
from fastapi import Request
from ..models.order import UpdateResponse
from functools import wraps
from ..s3.async_boto_wrapper import put_object, get_object, executor


def determine_status_code(message: str) -> int:
    if message in ["File updated successfully", "File written successfully"]:
        return 200
    elif message in ["damage_type is required", "Invalid combination of request parameters"]:
        return 400
    else:
        return 500


def decorator_damage_log(function: Callable):
    @wraps(function)
    async def wrapper(*args, **kwargs):
        request: Request = kwargs.get('request')
        damage_type = kwargs.get('damage_type')
        data_json = kwargs.get('data_json')
        client_ip = request.client.host if request else '127.0.0.1'
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if damage_type == "water":
            log_message = (f"[{current_time}] IP: {client_ip}, "
                           f"Damage Type: {damage_type}, DataJSON: {data_json}, ]")

        response = await function(*args, **kwargs)

        if damage_type == "water":
            log_response = (f"[{current_time}] Response Status: "
                            f"{determine_status_code(response.message) if isinstance(response, UpdateResponse) else 500}")

            log_content = log_message + "\n" + log_response + "\n"

            log_response = await get_object(
                Bucket=settings.s3_bucket_name,
                Key="log_update.log"
            )

            loop = asyncio.get_running_loop()
            log_data = await loop.run_in_executor(executor, log_response['Body'].read)

            log_content_bytes = log_content.encode('utf-8')
            new_log_data = log_data + log_content_bytes

            await put_object(
                Bucket=settings.s3_bucket_name,
                Key="log_update.log",
                Body=new_log_data
            )

        return response

    return wrapper
