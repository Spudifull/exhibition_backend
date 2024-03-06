from beanie import Document, PydanticObjectId


class FloorplanOrder(Document):
    virtualTourId: PydanticObjectId
    internalOrderId: int

    class Settings:
        name = "floorplanOrder"
