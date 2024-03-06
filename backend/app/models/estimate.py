from typing import Optional

from pydantic import BaseModel

from beanie import Document, PydanticObjectId


class Iteration(BaseModel):
    pdfFile: Optional[str] = None


class Estimate(Document):
    floorplanOrderId: PydanticObjectId
    iterations: list[Iteration]

    class Settings:
        name = "estimate"


class EstimateOrder(BaseModel):
    id: PydanticObjectId
    internalEstimateOrderId: Optional[str] = None


class EstimateOut(BaseModel):
    estimate_id: PydanticObjectId
    tour_id: PydanticObjectId
    fpo_internalOrderId: int
    pdfs: list[str]
