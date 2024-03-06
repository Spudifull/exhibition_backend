import enum
import logging

from pydantic import HttpUrl

from beanie import PydanticObjectId
from httpx import AsyncClient
from typing import Optional

from ..config import settings

log = logging.getLogger(__name__)


async def check_url(url: str) -> bool:
    async with AsyncClient() as client:
        try:
            response = await client.get(url)
        except Exception as e:
            log.warning(f"Exception {e} during request to {url}")
            return False
    return response.status_code == 200


@enum.unique
class ImageSize(enum.Enum):
    size_full = ""
    size_1080 = "1080-images/"
    size_150 = "150-images/"
    size_thumb = "thumb-images/"


class UrlBuilder:

    def __init__(self, user_identity: str, item_id: PydanticObjectId):
        self.user_identity = user_identity
        self.item_id = item_id
        self._initialize_urls()

    def _initialize_urls(self):
        self._base_http_url = (
            f"{settings.base_image_url}{self.user_identity}/{self.item_id}/Tour/"
        )
        self._base_json_url = (
            f"{settings.base_json_url}{self.user_identity}/{self.item_id}/Tour/"
        )
        self._base_s3_url = (
            f"{settings.s3_path_prefix}{self.user_identity}/{self.item_id}/Tour/"
        )
        self._base_http_url_for_picture = (
            f"{self._base_http_url}150-images/"
        )

    def get_img_url(self, img_size: ImageSize, filename: str) -> HttpUrl:
        return HttpUrl(f"{self._base_http_url}{img_size.value}{filename}")

    def get_s3_json_path(self, filename: str) -> str:
        return f"{self._base_s3_url}{filename}"

    def get_external_json_url(self, filename: str) -> HttpUrl:
        return HttpUrl(f"{self._base_json_url}{filename}")

    def get_base_http_url_for_picture(self, filename: str) -> HttpUrl:
        return HttpUrl(f"{self._base_http_url_for_picture}{filename}")

    @staticmethod
    def get_external_json_url_for_damage_file(file_name: str) -> HttpUrl:
        return HttpUrl(f"{settings.floorplan_service_url}{file_name}")

    @staticmethod
    def get_external_json_url_for_substitution_damage_file(damage_type: str,
                                                           filename: str,
                                                           type_substitution: str) -> HttpUrl:
        return HttpUrl(f"{settings.floorplan_service_url}"
                       f"/{damage_type}/{type_substitution}/{filename}.json")

    @staticmethod
    def get_internal_json_url_for_substitution_file(damage_type, filename: str,
                                                    type_substitution: str) -> str:
        return f"{damage_type}/{type_substitution}/{filename}.json"

    @staticmethod
    def get_internal_json_url_for_damage_file(damage_type: str) -> str:
        return f"{damage_type}/{damage_type}.json"

    @staticmethod
    def get_internal_damage_directory_url(damage_type: str) -> str:
        return f"{damage_type}/"

    @staticmethod
    def get_internal_other_damage_filename(damage_type: str, file_name: str) -> str:
        return f"{damage_type}/{file_name}.json"
