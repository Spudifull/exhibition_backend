from typing import Dict, Any

from beanie import PydanticObjectId

from ..models.area import AiMeAPIResponse, Area
from ..models.room import Room
from pprint import pprint


def traverse_areas(areas: list[Area], names: list[str]):
    for area in areas:
        name = area.AreaName.strip()
        if name in names:
            pprint(name)
            pprint(area)
            yield name, area
        if area.ChildAreas:
            yield from traverse_areas(area.ChildAreas, names)


def process_areas(resp: AiMeAPIResponse, rooms: list[Room]) -> dict[PydanticObjectId | None, Any]:
    room_names_to_ids = {room.name.strip(): room.id for room in rooms}
    return {
        room_names_to_ids[name]: area
        for name, area in traverse_areas(resp.Areas, list(room_names_to_ids.keys()))
    }
