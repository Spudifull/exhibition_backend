import pytest
from unittest.mock import AsyncMock
from starlette.exceptions import HTTPException
from backend.app.routers.order import (validate_file_type, process_file, get_order_builder_path,
                                       process_rooms_and_generate_urls)
from backend.app.external_apis.aime_api import AiMeAPIResponse
from backend.app.utils.url import UrlBuilder
from beanie import PydanticObjectId


@pytest.fixture
def mock_external_api_function(mocker: AsyncMock):
    return mocker.patch("backend.app.external_apis."
                        "aime_api.read_estimate_post_call", new_callable=AsyncMock)


@pytest.fixture
def mock_get_order_and_user_by_id(mocker):
    return mocker.patch("backend.app.routers.order."
                        "get_order_and_user_by_id", new_callable=AsyncMock)


@pytest.fixture
def mock_dependencies_for_rooms(mocker):
    mocker.patch("backend.app.routers.order.retrieve_order_rooms", new_callable=AsyncMock,
                 return_value=["room1", "room2"])
    mocker.patch("backend.app.routers.order.process_areas", return_value={"room1": "data1", "room2": "data2"})
    mocker.patch("backend.app.routers.order.process_room_and_generate_url", new_callable=AsyncMock,
                 return_value="https://example.com/room")


# Unit Test
@pytest.mark.asyncio
async def test_validate_file_type_success():
    try:
        await validate_file_type("application/pdf")
    except HTTPException:
        pytest.fail("HTTPException was invoked incorrectly")


@pytest.mark.asyncio
async def test_validate_file_type_failure():
    with pytest.raises(HTTPException) as exc_info:
        await validate_file_type("image/jpeg")

    assert exc_info.value.status_code == 400
    assert f"File content type must be application/pdf" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_process_file_success(mock_external_api_function):
    """
    TODO: create object example_response

    example_response = AiMeAPIResponse(
        ID=123,
        SubmittedFile="example.pdf",
        LineItemTotal=1500.0,
        LineItems=[],
        Areas=[],
    )
    """
    expected_response = AiMeAPIResponse()

    mock_external_api_function.return_value = expected_response

    result = await process_file("test.pdf", b"super_content")
    assert result == expected_response


@pytest.mark.asyncio
async def test_process_file_api_returns_none(mock_external_api_function):
    mock_external_api_function.return_value = None

    with pytest.raises(HTTPException) as exception_info:
        await process_file("test.pdf", b"content")

    assert exception_info.value.status_code == 500
    assert "File came empty from external API" in str(exception_info.value.detail)


@pytest.mark.asyncio
async def test_process_file_value_error(mock_external_api_function):
    mock_external_api_function.side_effect = ValueError

    with pytest.raises(HTTPException) as exception_info:
        await process_file("test.pdf", b"content")

    assert exception_info.value.status_code == 500
    assert "Failed to call external API" in str(exception_info.value.detail)


@pytest.mark.asyncio
async def test_get_order_builder_path_success(mock_get_order_and_user_by_id):
    """
    TODO: create object MockOrder and MockUser
    """
    mock_get_order_and_user_by_id.return_value = (MockOrder(), MockUser())
    value = PydanticObjectId("1")

    builder = await get_order_builder_path(value)
    assert isinstance(builder, UrlBuilder)


@pytest.mark.asyncio
async def test_get_order_builder_path_order_not_found(mock_get_order_and_user_by_id):
    mock_get_order_and_user_by_id.return_value = (None, MockUser())
    value = PydanticObjectId("10")

    with pytest.raises(HTTPException) as exception_info:
        await get_order_builder_path(value)
    assert exception_info.value.status_code == 404
    assert "order with id: nonexistent_order_id not found" in str(exception_info.value.detail)


@pytest.mark.asyncio
async def test_get_order_builder_path_user_not_found(mock_get_order_and_user_by_id):
    mock_get_order_and_user_by_id.return_value = (MockOrder(), None)
    value = PydanticObjectId("10")

    with pytest.raises(HTTPException) as exception_info:
        await get_order_builder_path(value)
    assert exception_info.value.status_code == 404
    assert "user with id: <USER_ID> not found" in str(exception_info.value.detail)


@pytest.mark.asyncio
async def test_process_rooms_with_available_rooms(mock_dependencies_for_rooms):
    value = PydanticObjectId("1")
    builder = UrlBuilder("user_identity", value)
    api_result = AiMeAPIResponse()

    urls = await process_rooms_and_generate_urls(value, api_result, builder)
    assert urls == ["https://example.com/room", "https://example.com/room"]


@pytest.mark.asyncio
async def test_process_rooms_without_rooms(mock_dependencies_for_rooms, mocker):
    value = PydanticObjectId("1")
    mocker.patch("backend.app.routers.order."
                 "retrieve_order_rooms", new_callable=AsyncMock, return_value=[])

    builder = UrlBuilder("user_identity", value)
    api_result = AiMeAPIResponse()
    urls = await process_rooms_and_generate_urls(value, api_result, builder)
    assert urls == []
