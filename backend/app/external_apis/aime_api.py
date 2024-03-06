from base64 import b64encode
import logging
from typing import Optional

from httpx import AsyncClient

from..models.area import AiMeAPIResponse
from ..config import settings

logger = logging.getLogger(__name__)


async def read_estimate_post_call(filename: str, content: bytes) -> Optional[AiMeAPIResponse]:
    logger.debug("The start of the READ_ESTIMATE_POST_CALL function")

    data = {
        "UserID": settings.aime_api_user_id,
        "FileName": filename,
        "CompanyCode": settings.aime_api_company_code,
        "Base64PdfString": str(b64encode(content), encoding="utf-8"),
    }
    api_url = settings.aime_api_url + "readestimate"
    
    async with AsyncClient() as client:
        try:
            response = await client.post(api_url, data=data)
        except Exception as e:
            logger.warning(f"Exception {e} during API call to {api_url}")
            return None
    if response.status_code == 200:
        return AiMeAPIResponse.model_validate(response.json())
    return None


