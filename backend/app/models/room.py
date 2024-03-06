from datetime import datetime
from typing import Optional

from pydantic import HttpUrl

from beanie import Document


# panorama
class Room(Document):
    filename: Optional[str] = None
    type: Optional[str] = None
    plan: Optional[int] = None
    name: Optional[str] = None
    limitedAccess: Optional[bool] = None
    isFirst: bool
    created: Optional[datetime] = None
    modified: Optional[datetime] = None
    imgUrlFull: Optional[HttpUrl] = None
    imgUrl150: Optional[HttpUrl] = None
    lineItemJsonUrl: Optional[HttpUrl] = None
    comment: Optional[str] = None
    requiresEstimate: Optional[bool] = None
