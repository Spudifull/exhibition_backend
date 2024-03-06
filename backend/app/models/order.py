from datetime import datetime
from typing import Optional, Any, Union, List, Tuple, Dict

from pydantic import BaseModel, HttpUrl, Field

from beanie import Document, PydanticObjectId

from .room import Room


class OrderId(Document):
    class Settings:
        name = "virtualTour"


class BaseOrder(OrderId):
    name: str
    userID: PydanticObjectId
    lineItemJsonUrl: Optional[HttpUrl] = None


class OrderPost(BaseOrder):
    created: datetime


class Order(BaseOrder):
    itemID: Optional[PydanticObjectId] = None
    modified: Optional[datetime] = None
    createdByUser: Optional[datetime] = None


class OrderWithRooms(BaseOrder):
    itemID: Optional[PydanticObjectId] = None
    panoramas: list[Room]


class OrderWithPicture(Order):
    url_picture: Optional[HttpUrl] = None


class PdfUploadResponse(BaseModel):
    order_id: PydanticObjectId
    claim_number: Optional[str]
    order_json_url: Optional[HttpUrl]
    rooms_json_urls: list[HttpUrl]


class OrderResponse(BaseModel):
    total_orders: int
    orders: list[Order]


class OrderResponseWithPicture(OrderResponse):
    orders: list[OrderWithPicture]


class UpdateResponse(BaseModel):
    message: str


class UpdateJSON(BaseModel):
    updates: dict = Field(...)


class JSONSubstitutionResponse(BaseModel):
    json_substitution_name: str = Field(..., description="The name of the Substitution "
                                                         "JSON file")
    json_substitution_body: Union[dict[str, Any], list[Any]] = Field(..., description="The body of the Substitution"
                                                                                      "JSON file")


class DamageContentResponse(BaseModel):
    name_damage: str
    url_damage_file: HttpUrl
    url_substitution_file: Optional[dict] = None


class UpdateResponseWithReport(UpdateResponse):
    validation_errors: Optional[List[Tuple[Dict[str, Any], str]]] = []


class UpdateResponseWithURL(UpdateResponse):
    json_url: HttpUrl
