import logging
import hashlib
import json

from typing import Optional, Self
from collections import defaultdict

from pydantic import BaseModel, Field, model_validator

from beanie import Document, PydanticObjectId

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


class LineItem(BaseModel):
    ID: Optional[str] = None
    UnitPrice: Optional[float] = None
    Category: str = Field(alias="cat")
    Selector: str = Field(alias="sel")
    Description: str = Field(alias="desc")
    Calculation: Optional[str] = None
    Quantity: Optional[str] = None
    Reset: Optional[float] = None
    Remove: Optional[float] = None
    Replace: Optional[float] = None
    Subtotal: Optional[float] = None
    OverheadProfit: Optional[float] = None
    Total: Optional[float] = None
    Action: Optional[str] = None
    Tax: Optional[float] = None
    Note: Optional[str] = None
    LineNumber: Optional[int] = None
    Unit: Optional[str] = None
    Position: Optional[dict] = None
    comments: Optional[list[str]] = None

    class Config:
        populate_by_name = True

    def __hash__(self):
        alias_mapping = {
            'cat': 'XactCAT',
            'sel': 'XactSelUSA',
            'desc': 'XactDescriptionUSA'
        }

        dict_to_hash = {
            alias_mapping[self.__fields__[field_name].alias]: getattr(self, field_name)
            for field_name in self.__fields__
            if self.__fields__[field_name].alias in alias_mapping
        }

        json_str = json.dumps(dict_to_hash)

        hash_object = hashlib.sha256(json_str.encode())

        return hash_object.hexdigest()

    @property
    def id(self):
        return self.__hash__()

    def __init__(self, **data):
        super().__init__(**data)
        if not self.ID:
            self.ID = self.id


class LineItemIn(LineItem):
    Category: str = Field(alias="cat")
    Selector: str = Field(alias="sel")
    Description: str = Field(alias="desc")


class Area(BaseModel):
    LineItems: list[LineItem]
    ChildAreas: list["Area"]
    areaType: Optional[str] = None
    AreaName: str
    SFWall: Optional[float] = None
    SFCeiling: Optional[float] = None
    SFWallsCeiling: Optional[float] = None
    SFFloor: Optional[float] = None
    SYFloor: Optional[float] = None
    LFFloor: Optional[float] = None
    LFCeiling: Optional[float] = None
    comment: Optional[str] = None
    isRequiresEstimate: Optional[bool] = None

    @model_validator(mode="after")
    def validate_line_items(self):
        log.info("Validate_line_items call")

        counts = {}
        updated_ids = {}

        for line_item in self.LineItems:
            counts[line_item.ID] = counts.get(line_item.ID, 0) + 1

        for line_item in self.LineItems:
            if counts[line_item.ID] > 1:
                updated_ids[line_item.ID] = updated_ids.get(line_item.ID, 0) + 1
                new_id = f"{line_item.ID}_{updated_ids[line_item.ID]}"
                line_item.ID = new_id

        return self


class AreaIn(Area):
    LineItems: list[LineItemIn]


class AiMeAPIResponse(BaseModel):
    ID: int
    Address: Optional[str] = None
    Claim: Optional[str] = None
    Client: Optional[str] = None
    SubmittedFile: str
    LineItemTotal: float
    City: Optional[str] = None
    Postal: Optional[str] = None
    LineItems: list[LineItem]
    Areas: list[Area]
