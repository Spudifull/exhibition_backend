import asyncio
import concurrent.futures
import functools

import boto3

from ..config import settings


executor = concurrent.futures.ThreadPoolExecutor()
s3 = boto3.client(
    "s3",
    aws_access_key_id=settings.s3_access_key_id,
    aws_secret_access_key=settings.s3_secret_access_key,
    region_name=settings.s3_region_name,
)


def aio(f):
    async def aio_wrapper(**kwargs):
        f_bound = functools.partial(f, **kwargs)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(executor, f_bound)

    return aio_wrapper


def aio_paginator(f):
    def sync_wrapper(**kwargs):
        paginator = f()

        results = []
        for page in paginator.paginate(**kwargs):
            results.extend([item for item in page.get("Contents", [])])

        return results

    async def aio_wrapper(**kwargs):
        loop = asyncio.get_running_loop()
        sync_partial_func = functools.partial(sync_wrapper, **kwargs)
        return await loop.run_in_executor(executor, sync_partial_func)

    return aio_wrapper


put_object = aio(s3.put_object)
get_object = aio(s3.get_object)
delete_object = aio(s3.delete_object)
list_objects = aio_paginator(functools.partial(s3.get_paginator, "list_objects_v2"))
delete_objects = aio(s3.delete_objects)
copy_object = aio(s3.copy_object)
directory_object = aio(s3.list_objects_v2)
