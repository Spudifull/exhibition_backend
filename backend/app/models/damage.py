import hashlib
import logging
import re
import json
from http import HTTPStatus

from typing import Optional, List, Tuple, Dict
from pydantic import BaseModel, Field, ValidationError
from fastapi import HTTPException
from starlette.status import (
    HTTP_400_BAD_REQUEST
)

logger = logging.getLogger(__name__)


class DamageLineItem(BaseModel):
    CAT: str = Field(..., alias="XactCAT")
    SEL: str = Field(..., alias="XactSelUSA")
    DESCRIPTION: str = Field(..., alias="XactDescriptionUSA")
    ACTIVITY: str = Field(default="", alias="XactActivityUSA")
    UNIT: str = Field(default="", alias="XactUnitUSA")
    CATEGORY: str = Field(default="", alias="XactCategoryName")
    Id: Optional[str] = Field(default=None, alias="Id")
    SELECTED: Optional[bool] = Field(default=None, alias="selected")
    SUBDAMAGESELECTED: Optional[bool] = Field(default=None, alias="subDamageSelected")
    COLUMNORDER: Optional[list] = Field(default_factory=list, alias="columnOrder")
    filters: Optional[list[dict]] = Field(default_factory=list, alias="filters")
    FILTERSORDER: Optional[list] = Field(default_factory=list, alias="filtersOrder")

    class Config:
        extra = "forbid"

    def __init__(self, **data):
        super().__init__(**data)
        if not self.Id:
            self.Id = self.generate_id()

    def generate_id(self):
        selected_aliases = ['XactCAT', 'XactSelUSA', 'XactDescriptionUSA']

        attrs_with_aliases = {
            self.__fields__[field_name].alias: getattr(self, field_name)
            for field_name in self.__fields__ if self.__fields__[field_name].alias in selected_aliases
        }

        json_str = json.dumps(attrs_with_aliases)

        hash_object = hashlib.sha256(json_str.encode())

        return hash_object.hexdigest()


class DamageLineItemList:
    def __init__(self, data: List[dict]):
        self.damage_line_items: List[DamageLineItem] = []
        self.invalid_items: List[Tuple[Dict, str]] = []
        self.validate_damage_line_items(data)

    def validate_damage_line_items(self, damage_line_items: List[dict]):
        for item in damage_line_items:
            try:
                valid_item = DamageLineItem(**item)
                self.damage_line_items.append(valid_item)
            except ValidationError as e:
                error_str = DamageLineItemList.extract_error_details(e)
                self.invalid_items.append((item, error_str))

    def get_validation_result(self):
        valid_items_dicts = [item.dict(by_alias=True, exclude_none=True) for item in self.damage_line_items]
        filtered_list_of_dicts = [{k: v for k, v in d.items() if v not in
                                   [None, [], {}]} for d in valid_items_dicts]

        if not filtered_list_of_dicts:
            logger.error(
                "There is not a single valid item in the received data"
            )

            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail="There is not a single valid item in the received data"
            )

        return {
            "valid_items": filtered_list_of_dicts,
            "invalid_items": self.invalid_items,
        }

    @staticmethod
    def extract_error_details(e: ValidationError):
        error_messages = [
            (f"Field: {error.get('loc', ['Unknown'])[0]}, "
             f"Reason: {error.get('msg', 'Unknown reason')}")
            for error in e.errors()
        ]

        return "\n".join(error_messages) if error_messages \
            else "Error details could not be extracted"
