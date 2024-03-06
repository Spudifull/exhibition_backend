import pytest
import logging
import json

from beanie import PydanticObjectId
from httpx import AsyncClient

from backend.app.models.area import AiMeAPIResponse
from fastapi.testclient import TestClient
from fastapi import HTTPException
from io import BytesIO
from pytest import fixture
from backend.app.s3.file_ops import (get_json_from_s3,
                                     check_file_exists_in_s3)
from unittest.mock import patch, AsyncMock

from backend.app.utils.url import UrlBuilder

logger = logging.getLogger(__name__)

test_external_api_data = '''
{
  "ID": 113,
  "Address": "TEST_DATA",
  "Claim": "113",
  "Client": "TEST_DATA",
  "SubmittedFile": "TEST_DATA",
  "LineItemTotal": 113,
  "City": "TEST_DATA",
  "Postal": "113",
  "LineItems": [],
  "Areas": [
    {
      "LineItems": [],
      "ChildAreas": [
        {
          "LineItems": [
            {
              "UnitPrice": 0,
              "cat": "TEST_DATA",
              "sel": "TEST_DATA",
              "desc": "TEST_DATA",
              "Calculation": "F",
              "Quantity": "514.66",
              "Reset": 0,
              "Remove": 0,
              "Replace": 0.32,
              "Subtotal": 0,
              "OverheadProfit": 33.96,
              "Total": 203.75,
              "Action": "+",
              "Tax": 5.1,
              "Note": "TEST_DATA",
              "LineNumber": 1,
              "Unit": "SF",
              "Position": null
            }
          ],
          "ChildAreas": [],
          "areaType": null,
          "AreaName": "TEST_DATA",
          "SFWall": 381.07,
          "SFCeiling": 500.61,
          "SFWallsCeiling": 881.68,
          "SFFloor": 500.61,
          "SYFloor": 55.62,
          "LFFloor": 46.63,
          "LFCeiling": 59.88
        }
      ],
      "areaType": "TEST_DATA",
      "AreaName": "TEST_DATA",
      "SFWall": null,
      "SFCeiling": null,
      "SFWallsCeiling": null,
      "SFFloor": null,
      "SYFloor": null,
      "LFFloor": null,
      "LFCeiling": null
    }
  ]
}
'''

external_data = json.loads(test_external_api_data)
object_external_api = AiMeAPIResponse.model_validate(external_data)

ids_virtualTour = (
    "615e9c55a67fb455bafbef6b", "6180f99bc3fb131d1daae4bd", "6180f9eac3fb131d1daae4c2", "618148b4ad53664dd04bb647",
    "61814aa7ad53664dd04bb652", "6188eeedb7b5ba2a82126c0f", "6188ef61b7b5ba2a82126c11", "6188efbcb7b5ba2a82126c17",
    "618a3465b7b5ba2a82126e74")

test_data = {"_id": "615e9c55a67fb455bafbef6b",
             "userID": "615bfd5ce012e2215df19db8",
             "name": "Test_19223",
             "modified": "2022-02-15T13:22:26.506+0000",
             "itemID": "615e9c55a67fb455bafbef6c",
             "panoramas": [
                 {
                     "_id": "615e9c5fa67fb455bafbef6f",
                     "filename": "srv_27i4qb3yr1.JPG",
                 },
                 {
                     "_id": "6180fd1bc3fb131d1daae4cc",
                     "filename": "5p0dbr7o0d.JPG",
                 },
             ]
             }

"""
TODO DON`T WORK FIXTURE FOR MOCK TESTS.
"""


@fixture
def client():
    from backend.app.app import app
    application = app
    with TestClient(application) as test_client:
        yield test_client


@pytest.mark.asyncio
async def test_get_orders_with_default_value(client):
    response = client.get("/orders/", )

    data_response = response.json()
    orders = data_response['orders']
    try:
        index_in_response = next(i for i, row in enumerate(orders) if row["_id"] == test_data["_id"])
    except StopIteration:
        assert False

    assert response.status_code == 200
    assert len(data_response['orders']) == 9
    assert orders[index_in_response]["_id"] == test_data["_id"]
    assert orders[index_in_response]["userID"] == test_data["userID"]
    assert orders[index_in_response]["name"] == test_data["name"]
    assert orders[index_in_response]["itemID"] == test_data["itemID"]


@pytest.mark.asyncio
async def test_get_orders_with_no_default_value(client):
    response = client.get("/orders/", params={'limit': 3, 'offset': 1})
    assert response.status_code == 200

    data_response = response.json()

    assert 'total_orders' in data_response
    assert 'orders' in data_response
    assert 'url_pictures' in data_response

    orders = data_response['orders']
    assert len(orders) == 3

    # Added a default test, you can make it more meaningful
    url_pictures = data_response['url_pictures']
    assert len(url_pictures) == 3

    ids = ids_virtualTour

    counter = sum(order["_id"] in ids for order in orders)
    assert counter == 3


@pytest.mark.asyncio
async def test_get_orders_with_no_default_value_and_include_total(client):
    response = client.get("/orders/", params={'limit': 3, 'offset': 1})

    assert response.status_code == 200

    data_response = response.json()
    assert 'total_orders' in data_response
    assert 'orders' in data_response
    assert 'url_pictures' in data_response

    orders = data_response['orders']
    assert len(orders) == 3

    # Added a default test, you can make it more meaningful
    url_pictures = data_response['url_pictures']
    assert len(url_pictures) == 3

    assert data_response['total_orders'] == 9

    ids = ids_virtualTour
    counter = sum(order["_id"] in ids for order in orders)
    assert counter == 3


@pytest.mark.asyncio
async def test_get_order_ids_with_default_value(client):
    response = client.get("/orders/ids")
    ids = ids_virtualTour
    data_response = response.json()
    for id in data_response:
        if id not in ids:
            assert False

    assert response.status_code == 200
    assert len(data_response) == 9


@pytest.mark.asyncio
async def test_get_order_ids_with_no_default_value_with_end_offset(client):
    response = client.get("/orders/ids", params={'limit': 3, 'offset': 7})
    ids = ids_virtualTour
    data_response = response.json()
    counter = 0
    for id in data_response:
        if id in ids:
            counter += 1

    assert response.status_code == 200
    assert len(response.json()) == 2
    assert counter == 2


@pytest.mark.asyncio
async def test_get_order_by_id(client):
    response = client.get(f"/orders/{test_data['_id']}")
    data_response = response.json()

    assert response.status_code == 200
    assert data_response["_id"] == test_data["_id"]
    assert data_response["userID"] == test_data["userID"]
    assert data_response["name"] == test_data["name"]
    assert data_response["itemID"] == test_data["itemID"]


@pytest.mark.asyncio
async def test_get_order_by_n_exists_id(client):
    response = client.get(f"/orders/615e9c55a67fb455bafbef6c")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_orders_by_user_id(client):
    response = client.get(f"/orders/by_user_id/{test_data['userID']}", params={'limit': 10, 'offset': 0})
    data_response = response.json()
    assert 'total_orders' in data_response
    assert 'orders' in data_response

    for row in data_response['orders']:
        if row["_id"] == test_data["_id"]:
            break
    else:
        assert False

    assert response.status_code == 200
    assert len(data_response['orders']) >= 1


@pytest.mark.asyncio
async def test_get_orders_by_user_id(client):
    response = client.get(f"/orders/by_user_id/{test_data['userID']}/ids", params={'limit': 10, 'offset': 0})
    data_response = response.json()
    for id in data_response:
        if id == test_data["_id"]:
            break
    else:
        assert False

    assert response.status_code == 200
    assert len(data_response) >= 1


@pytest.mark.asyncio
async def test_get_orders_ids_by_user_id(client):
    response = client.get(f"/orders/by_user_id/{test_data['userID']}/count")
    data_response = response.json()

    assert response.status_code == 200
    assert data_response == 6


@pytest.mark.asyncio
async def test_get_rooms_in_order(client):
    response = client.get(f"/orders/{test_data['_id']}/rooms")
    data_response = response.json()
    ids = [row["_id"] for row in test_data["panoramas"]]
    for room in data_response:
        if room["_id"] not in ids:
            assert False

    assert response.status_code == 200
    assert len(test_data["panoramas"]) == len(data_response)


@pytest.mark.asyncio
async def test_get_order_preview(client):
    response = client.get(f"/orders/{test_data['_id']}/preview")
    data_response = response.json()

    assert response.status_code == 200
    assert test_data["panoramas"][0]["filename"] == data_response.rsplit('/')[-1]


@pytest.mark.asyncio
@patch(
    target='backend.app.s3.file_ops.get_json_from_s3',
    new_callable=AsyncMock
)
@patch(
    target='backend.app.s3.file_ops.update_json_file',
    new_callable=AsyncMock
)
@patch(
    target="backend.app.routers.order.get_order_builder_path",
    new_callable=AsyncMock
)
async def test_update_json_result_file(mock_get_order_builder_path,
                                       mock_update_json_file,
                                       mock_get_json_from_s3, client):
    test_order_id = "615e9c55a67fb455bafbef6b"

    test_updates = {"updates": {"key": "value"}}

    mock_get_order_builder_path.return_value = UrlBuilder("615bfd5ce",
                                                          PydanticObjectId("615e9c55a67fb455bafbef6c"))
    mock_update_json_file.return_value = {'ResponseMetadata': {'HTTPStatusCode': 200}}
    mock_get_json_from_s3.return_value = test_updates

    response = client.put(
        url=f"/orders/change_result_json/{test_order_id}",
        json=test_updates
    )

    assert response.status_code == 200
    data = response.json()
    assert data['message'] == "File updated successfully"


@pytest.mark.asyncio
@patch(
    target='backend.app.s3.file_ops.delete_object',
    new_callable=AsyncMock
)
@patch(
    target="backend.app.routers.order.get_order_builder_path",
    new_callable=AsyncMock
)
async def test_get_orders_with_no_default_value(mock_delete_object,
                                                mock_builder_path, client):
    test_order_id = "615e9c55a67fb455bafbef6b"

    mock_delete_object.return_value.put_object.return_value = {'ResponseMetadata': {'HTTPStatusCode': 200}}
    mock_builder_path.return_value = UrlBuilder("615bfd5ce",
                                                PydanticObjectId("615e9c55a67fb455bafbef6c"))

    response = client.delete(
        url=f"/orders/delete_result_json/{test_order_id}"
    )

    assert response.status_code == 200
    data = response.json()
    assert data['message'] == "File deleted successfully"

    mock_builder_path.assert_called_once_with()
    mock_delete_object.assert_called_once()


@pytest.mark.asyncio
@patch(
    target='backend.app.s3.file_ops.put_object',
    new_callable=AsyncMock
)
@patch(
    target='backend.app.routers.order.get_order_builder_path',
    new_callable=AsyncMock
)
@patch(
    target='backend.app.routers.order.read_estimate_post_call',
    new_callable=AsyncMock
)
async def test_upload_pdf_to_order(mock_read_estimate_post_call,
                                   mock_builder_path, mock_put_object,
                                   client):
    test_order_id = "615e9c55a67fb455bafbef6b"
    mock_read_estimate_post_call.return_value = object_external_api
    mock_builder_path.return_value = UrlBuilder("615bfd5ce",
                                                PydanticObjectId("615e9c55a67fb455bafbef6c"))
    mock_put_object.return_value = {
        'ResponseMetadata': {
            'RequestId': '1234567890EXAMPLE',
            'HostId': 'EXAMPLEHostId',
            'HTTPStatusCode': 200,
            'HTTPHeaders': {
                'x-amz-id-2': 'EXAMPLE123/5678abcdefghijklambdaisawesome/mnopqrstuvwxyzABCDEFGH',
                'x-amz-request-id': '1234567890EXAMPLE',
                'date': 'Wed, 05 Oct 2016 03:23:22 GMT',
                'etag': '"9b2cf535f27731c974343645a3985328"',
                'content-length': '0',
                'server': 'AmazonS3'
            },
            'RetryAttempts': 0
        }
    }

    test_pdf_content = BytesIO(b'%PDF-1.4\n1 0 obj\n<</Type /Catalog>>\nend obj\ntrailer\n<</Root 1 0 R>>\n%%EOF')
    test_pdf_content.name = "test.pdf"

    response = client.post(
        f"/orders/{test_order_id}/upload_pdf",
        files={"file": ("test.pdf", test_pdf_content, "application/pdf")}
    )

    assert response.status_code == 200

    response_data = response.json()
    assert response_data["order_id"] == test_order_id
    assert response_data["order_json_url"] == (f"https://floorplan-info45.s3.amazonaws.com/ai-estimator/storage/images"
                                               f"/v1/items/615bfd5ce/615e9c55a67fb455bafbef6c/Tour/result.json")
    assert response_data["rooms_json_urls"] == []


@pytest.mark.asyncio
@patch(
    target='backend.app.s3.file_ops.put_object',
    new_callable=AsyncMock
)
@patch(
    target='backend.app.routers.order.get_order_builder_path',
    new_callable=AsyncMock
)
@patch(
    target='backend.app.routers.order.get_single_order_ids_by_claim_number',
    new_callable=AsyncMock
)
@patch(
    target='backend.app.routers.order.read_estimate_post_call',
    new_callable=AsyncMock
)
async def test_upload_pdf(mock_read_estimate_post_call, mock_retrieve_claim,
                          mock_builder_path, mock_put_object, client):
    mock_read_estimate_post_call.return_value = object_external_api
    mock_retrieve_claim.return_value = PydanticObjectId("615e9c55a67fb455bafbef6b")
    mock_builder_path.return_value = UrlBuilder("615bfd5ce",
                                                PydanticObjectId("615e9c55a67fb455bafbef6c"))
    mock_put_object.return_value = {
        'ResponseMetadata': {
            'RequestId': '1234567890EXAMPLE',
            'HostId': 'EXAMPLEHostId',
            'HTTPStatusCode': 200,
            'HTTPHeaders': {
                'x-amz-id-2': 'EXAMPLE123/5678abcdefghijklambdaisawesome/mnopqrstuvwxyzABCDEFGH',
                'x-amz-request-id': '1234567890EXAMPLE',
                'date': 'Wed, 05 Oct 2016 03:23:22 GMT',
                'etag': '"9b2cf535f27731c974343645a3985328"',
                'content-length': '0',
                'server': 'AmazonS3'
            },
            'RetryAttempts': 0
        }
    }

    test_pdf_content = BytesIO(b'%PDF-1.4\n1 0 obj\n<</Type /Catalog>>\nend obj\ntrailer\n<</Root 1 0 R>>\n%%EOF')
    test_pdf_content.name = "test.pdf"

    response = client.post(
        url="/orders/upload_pdf",
        files={"file": ("test.pdf", test_pdf_content, "application/pdf")}
    )

    mock_read_estimate_post_call.assert_called_once()
    mock_put_object.assert_called_once()
    assert response.status_code == 200

    response_data = response.json()
    assert response_data["order_id"] == "615e9c55a67fb455bafbef6b"
    assert response_data["order_json_url"] == (f"https://floorplan-info45.s3.amazonaws.com/ai-estimator/storage/images"
                                               f"/v1/items/615bfd5ce/615e9c55a67fb455bafbef6c/Tour/result.json")
    assert response_data["rooms_json_urls"] == []


@pytest.mark.asyncio
async def test_create_delete_damage_json_success(client):
    response_create = client.put(
        url=f"/orders/save_damage_json/",
        json={"damage_type": "test",
              "data_json": {
                  "test": "test_data"
              }
              }
    )

    assert response_create.status_code == 200
    response_data = response_create.json()
    assert response_data["message"] == "File updated successfully"

    check_create_file = await check_file_exists_in_s3("test.json")
    assert check_create_file is True

    response_delete = client.delete(
        url=f"/orders/delete_damage_json/test"
    )

    assert response_delete.status_code == 200
    response_data = response_delete.json()
    assert response_data["message"] == "File deleted successfully"

    check_delete_file = await check_file_exists_in_s3("test.json")
    assert check_delete_file is False


@pytest.mark.asyncio
async def test_update_list_damage_file(client):
    real_data = await get_json_from_s3(
        s3_path="damage_type.json"
    )

    response_update = client.put(
        url=f"orders/save_damage_json/",
        json={"list_damage_json": {"types": ["new_test_data"]}}
    )

    assert response_update.status_code == 200
    response_data = response_update.json()
    assert response_data["message"] == "File updated successfully"

    check_update_file = await get_json_from_s3(
        s3_path="damage_type.json"
    )

    assert check_update_file == {"types": ["new_test_date"]}

    response_return = client.put(
        url=f"orders/save_damage_json/",
        json={"list_damage_json": real_data}
    )

    assert response_return.status_code == 200


@pytest.mark.asyncio
async def test_update_list_damage_json_error(client):
    error_response = {'detail': "Failed to update result.json file: 400: Invalid request parameters"}

    response_update = client.put(
        url=f"/orders/save_damage_json/",
    )

    assert response_update.status_code == 500
    response_data = response_update.json()
    assert response_data == error_response


@pytest.mark.asyncio
async def test_update_damage_json_error(client):
    error_response = {"detail": "Failed to update result.json file: 400: damage_type is required"}

    response_update = client.put(
        url=f"/orders/save_damage_json/",
        json={"damage_type": "",
              "data_json": {
                  "test": "test_data"
              }
              }
    )

    assert response_update.status_code == 500
    response_data = response_update.json()
    assert response_data == error_response


@pytest.mark.asyncio
async def test_update_damage_file(client):
    response_get = client.put(
        url=f"/orders/update_damage_file/",
        json={
            "damage_type": "backend_test",
            "data_json": [
                {
                    "filters": [],
                    "XactCAT": "WTR",
                    "XactSelUSA": "ULAYSNA",
                    "XactDescriptionUSA": "Tear out non-salv underlayment, no bagging - Cat 3 - a/hrs",
                    "XactActivityUSA": "-",
                    "XactUnitUSA": "SF",
                    "XactCategoryName": "Water Extraction & remediation",
                    "Id": "fc49c978373c9b2fbcc60cc86a03448686e0785fc388b09ef68013d5632611e9",
                    "filtersOrder": []
                }
            ]
        }
    )

    assert response_get.status_code == 200


@pytest.mark.asyncio
@patch(
    target='backend.app.routers.order.get_file_name_s3_folder',
    new_callable=AsyncMock
)
async def test_get_contents_damage_directories(get_file, client: TestClient):
    test_damage = "test_backend"
    get_file.return_value = ["test_backend/test_backend.json",
                             "test_backend/subtype/test_subtype_backend.json",
                             "test_backend/group/test_group_backend.json"]

    response_get = client.get(
        url=f"/orders/get_contents_damage_directory/{test_damage}",
    )

    expected_response = {
        "name_damage": "test_backend",
        "url_damage_file": "https://my-backet.s3.amazonaws.com/"
                           "test_backend/test_backend.json",
        "url_substitution_file": {
            "subtype": [
                "https://my-backet.s3.amazonaws.com/"
                "test_backend/subtype/test_subtype_backend.json"
            ],
            "group": [
                "https://my-backet.s3.amazonaws.com/"
                "test_backend/group/test_group_backend.json"
            ]
        }
    }
    assert response_get.status_code == 200
    response_data = response_get.json()
    assert response_data == expected_response


@pytest.mark.asyncio
@patch(
    target='backend.app.routers.order.get_contents_damage_directory',
    new_callable=AsyncMock
)
async def test_get_contents_damage_directory_failure(get_contents, client: AsyncClient):
    test_damage = "test_backend"
    get_contents.side_effect = HTTPException(
        status_code=404,
        detail="Directory not found"
    )

    response_get = client.get(
        url=f"/orders/get_contents_damage_directory/{test_damage}",
    )

    expected_response = "Directory not found"

    assert response_get.status_code == 404
    response_data = response_get.json()
    assert response_data['detail'] == expected_response


@pytest.mark.asyncio
@patch(
    target='backend.app.s3.file_ops.write_json_file'
)
@patch(
    target='backend.app.s3.file_ops.get_json_from_s3'
)
async def test_update_damage_json_create(get_json, put_json, client: AsyncClient):
    get_json.side_effect = HTTPException(
        status_code=404,
        detail="File not found"
    )

    put_json.return_value = {
        "message": "File updated successfully"
    }

    response_put = client.put(
        url=f"orders/update_damage_file/",
        json={
            "damage_type": "test_backend",
            "data_json": [
                {
                    "XactActivityUSA": "+",
                    "XactCAT": "Test",
                    "XactCategoryName": "Accessories - Test",
                    "XactDescriptionUSA": "Accessories - Test",
                    "XactSelUSA": "TES",
                    "XactUnitUSA": "US"
                },
                {
                    "XactActivityUSA": "-",
                    "XactCAT": "REAL",
                    "XactCategoryName": "Accessories - Test",
                    "XactDescriptionUSA": "Accessories - Test",
                    "XactSelUSA": "LAS",
                    "XactUnitUSA": "US"
                }
            ]
        }
    )

    put_json.assert_called_once_with(
        srt_data=[
            {
                'XactCAT': 'Test',
                'XactSelUSA': 'TES',
                'XactDescriptionUSA': 'Accessories - Test',
                'XactActivityUSA': '+',
                'XactUnitUSA': 'US',
                'XactCategoryName': 'Accessories - Test',
                'Id': 'b7f0992bd071ae4fc2874872aa32860331248ef2063c3e3565864a642e853b42'
            },
            {
                'XactCAT': 'REAL',
                'XactSelUSA': 'LAS',
                'XactDescriptionUSA': 'Accessories - Test',
                'XactActivityUSA': '-',
                'XactUnitUSA': 'US',
                'XactCategoryName': 'Accessories - Test',
                'Id': '8f302e9b209f4a6296ba331a7441832844771e2060d51299f84fd358085a3a92'
            }
        ],
        s3_path='test_backend/test_backend.json'
    )

    assert response_put.status_code == 200
    response_data = response_put.json()
    assert response_data["message"] == "File updated successfully"


@pytest.mark.asyncio
@patch(
    target='backend.app.s3.file_ops.write_json_file'
)
@patch(
    target='backend.app.s3.file_ops.get_json_from_s3'
)
@patch(
    target='backend.app.s3.file_ops.copy_object'
)
async def test_put_order(copy_object, get_json, put_json, client: AsyncClient):
    copy_object.return_value = {
        "message": "Successfully copied"
    }

    get_json.side_effect = HTTPException(
        status_code=404,
        detail="File not found"
    )

    put_json.return_value = {
        "message": "File updated successfully"
    }

    response_put = client.put(
        url="orders/update_damage_file/",
        json={
            "damage_type": "test_backend",
            "substitution_type": "group",
            "substitution_json": {
                "json_substitution_name": "test_group_backend",
                "json_substitution_body": [
                    {
                        "XactActivityUSA": "+",
                        "XactCAT": "Test",
                        "XactCategoryName": "Accessories - Test",
                        "XactDescriptionUSA": "Accessories - Test",
                        "XactSelUSA": "TES",
                        "XactUnitUSA": "US"
                    },
                    {
                        "XactActivityUSA": "-",
                        "XactCAT": "REAL",
                        "XactCategoryName": "Accessories - Test",
                        "XactDescriptionUSA": "Accessories - Test",
                        "XactSelUSA": "LAS",
                        "XactUnitUSA": "US"
                    }
                ]
            }
        }
    )

    put_json.assert_called_once_with(
        srt_data=[
            {
                'XactCAT': 'Test',
                'XactSelUSA': 'TES',
                'XactDescriptionUSA': 'Accessories - Test',
                'XactActivityUSA': '+',
                'XactUnitUSA': 'US',
                'XactCategoryName': 'Accessories - Test',
                'Id': 'b7f0992bd071ae4fc2874872aa32860331248ef2063c3e3565864a642e853b42'
            },
            {
                'XactCAT': 'REAL',
                'XactSelUSA': 'LAS',
                'XactDescriptionUSA': 'Accessories - Test',
                'XactActivityUSA': '-',
                'XactUnitUSA': 'US',
                'XactCategoryName': 'Accessories - Test',
                'Id': '8f302e9b209f4a6296ba331a7441832844771e2060d51299f84fd358085a3a92'
            }
        ],
        s3_path='test_backend/group/test_group_backend.json'
    )

    assert response_put.status_code == 200
    response_data = response_put.json()
    assert response_data["message"] == "Updated successfully damage file"


@pytest.mark.asyncio
@patch(
    target='backend.app.routers.order.write_json_file'
)
@patch(
    target='backend.app.routers.order.get_json_from_s3'
)
@patch(
    target='backend.app.s3.file_ops.copy_object'
)
async def test_update_all_line_items_json(copy, get_json, put_json, client: AsyncClient):
    copy.return_value = "Successfully copied"

    get_json.return_value = [
        {
            'XactCAT': 'Test',
            'XactSelUSA': 'TES',
            'XactDescriptionUSA': 'Accessories - Test',
            'XactActivityUSA': '+',
            'XactUnitUSA': 'US',
            'XactCategoryName': 'Accessories - Test',
            'Id': 'b7f0992bd071ae4fc2874872aa32860331248ef2063c3e3565864a642e853b42'
        },
        {
            'XactCAT': 'PREAF',
            'XactSelUSA': 'LASOR',
            'XactDescriptionUSA': 'Accessories - Test',
            'XactActivityUSA': '-',
            'XactUnitUSA': 'US',
            'XactCategoryName': 'Accessories - Test',
            'Id': '8f302e9c609f4a6296ba331a7441832844771e2060d51299f84fd358085a3a92'
        }
    ]

    put_json.return_value = {
        "message": "File updated successfully"
    }

    response_put = client.put(
        url="orders/update_all_line_items_json",
        json=[
            {
                "XactActivityUSA": '+',
                "XactCAT": 'Test',
                "XactCategoryName": 'Accessories - Test',
                "XactDescriptionUSA": 'Accessories - Test',
                "XactSelUSA": 'TES',
                "XactUnitUSA": None
            },
            {
                "XactActivityUSA": "-",
                "XactCAT": "REAL",
                "XactCategoryName": "Accessories - Test",
                "XactDescriptionUSA": "Accessories - Test",
                "XactSelUSA": "LAS",
                "XactUnitUSA": "US"
            }
        ]
    )

    put_json.assert_called_once_with(
        srt_data=[
            {
                'XactCAT': 'Test',
                'XactSelUSA': 'TES',
                'XactDescriptionUSA': 'Accessories - Test',
                'XactActivityUSA': '+',
                'XactUnitUSA': 'US',
                'XactCategoryName': 'Accessories - Test',
                'Id': 'b7f0992bd071ae4fc2874872aa32860331248ef2063c3e3565864a642e853b42'},
            {
                'XactCAT': 'PREAF',
                'XactSelUSA': 'LASOR',
                'XactDescriptionUSA': 'Accessories - Test',
                'XactActivityUSA': '-',
                'XactUnitUSA': 'US',
                'XactCategoryName': 'Accessories - Test',
                'Id': '8f302e9c609f4a6296ba331a7441832844771e2060d51299f84fd358085a3a92'},
            {
                'XactCAT': 'REAL',
                'XactSelUSA': 'LAS',
                'XactDescriptionUSA': 'Accessories - Test',
                'XactActivityUSA': '-',
                'XactUnitUSA': 'US',
                'XactCategoryName': 'Accessories - Test',
                'Id': '8f302e9b209f4a6296ba331a7441832844771e2060d51299f84fd358085a3a92'
            }
        ],
        s3_path='TrainAllLineItems.json'
    )

    assert response_put.status_code == 200
    response_data = response_put.json()
    assert response_data["message"] == "Successfully updated AllLineItems.json"


@pytest.mark.asyncio
@patch(
    target='backend.app.routers.order.write_json_file'
)
@patch(
    target='backend.app.routers.order.get_json_from_s3'
)
@patch(
    target='backend.app.routers.order.update_backup'
)
async def test_invalid_return_item_in_all_line_items_json(
        backup_file, get_json, put_json, client
):
    get_json.return_value = [
        {
            'XactCAT': 'Test',
            'XactSelUSA': 'TES',
            'XactDescriptionUSA': 'Accessories - Test',
            'XactActivityUSA': '+',
            'XactUnitUSA': 'US',
            'XactCategoryName': 'Accessories - Test',
            'Id': 'b7f0992bd071ae4fc2874872aa32860331248ef2063c3e3565864a642e853b42'
        },
        {
            'XactCAT': 'PREAF',
            'XactSelUSA': 'LASOR',
            'XactDescriptionUSA': 'Accessories - Test',
            'XactActivityUSA': '-',
            'XactUnitUSA': 'US',
            'XactCategoryName': 'Accessories - Test',
            'Id': '8f302e9c609f4a6296ba331a7441832844771e2060d51299f84fd358085a3a92'
        }
    ]

    put_json.return_value = {
        "message": "File updated successfully"
    }

    backup_file.return_value = {
        "message": "Successfully copied"
    }

    response_put = client.put(
        url="orders/update_all_line_items_json",
        json=[
            {
                "XactActivityUSA": 1,
                "XactCAT": 'Test',
                "XactCategoryName": 'Accessories - Test',
                "XactDescriptionUSA": 'Accessories - Test',
                "XactSelUSA": 'TES',
                "XactUnitUSA": 'US'
            },
            {
                "XactActivityUSA": "-",
                "XactCAT": "REAL",
                "XactCategoryName": "Accessories - Test",
                "XactDescriptionUSA": "Accessories - Test",
                "XactSelUSA": "LAS",
                "XactUnitUSA": "US"
            }
        ]
    )

    assert response_put.status_code == 200
    response_data = response_put.json()
    logger.info(response_data)
    assert response_data["error_validation"][0][1] == 'Field: XactActivityUSA, Reason: Input should be a valid string'


@pytest.mark.asyncio
@patch(
    target='backend.app.routers.order.write_json_file'
)
async def test_set_all_line_items(put_json: AsyncMock, client: AsyncClient):
    put_json.return_value = {
        'message': "File updated successfully"
    }

    response_put = client.put(
        url="orders/set_all_line_items",
        json=[
            {
                "XactActivityUSA": "+",
                "XactCAT": "Test",
                "XactCategoryName": "Accessories - Test",
                "XactDescriptionUSA": "Accessories - Test",
                "XactSelUSA": "TES",
                "XactUnitUSA": "US"
            },
            {
                "XactActivityUSA": "-",
                "XactCAT": "REAL",
                "XactCategoryName": "Accessories - Test",
                "XactDescriptionUSA": "Accessories - Test",
                "XactSelUSA": "LAS",
                "XactUnitUSA": "US"
            }
        ]
    )

    put_json.assert_called_once_with(
        srt_data=[
            {
                'XactCAT': 'Test',
                'XactSelUSA': 'TES',
                'XactDescriptionUSA': 'Accessories - Test',
                'XactActivityUSA': '+',
                'XactUnitUSA': 'US',
                'XactCategoryName': 'Accessories - Test',
                'Id': 'b7f0992bd071ae4fc2874872aa32860331248ef2063c3e3565864a642e853b42'
            },
            {
                'XactCAT': 'REAL',
                'XactSelUSA': 'LAS',
                'XactDescriptionUSA': 'Accessories - Test',
                'XactActivityUSA': '-',
                'XactUnitUSA': 'US',
                'XactCategoryName': 'Accessories - Test',
                'Id': '8f302e9b209f4a6296ba331a7441832844771e2060d51299f84fd358085a3a92'
            }
        ],

        s3_path='TrainAllLineItems.json'
    )

    assert response_put.status_code == 200
    response_data = response_put.json()
    assert response_data["message"] == "Successfully updated AllLineitems.json"


@pytest.mark.asyncio
async def test_set_all_line_items_failure_validation(client: AsyncClient):
    response_put = client.put(
        url="orders/set_all_line_items",
        json=[
            {
                "XactActivityUSA": 1,
                "XactCAT": "Test",
                "XactCategoryName": "Accessories - Test",
                "XactDescriptionUSA": "Accessories - Test",
                "XactSelUSA": "TES",
                "XactUnitUSA": "US"
            }
        ]
    )

    assert response_put.status_code == 400
    response_data = response_put.json()
    assert "Invalid validation for line_items: index 0" in response_data['detail']

    error_details = response_data['detail']
    assert any(
        "Input should be a valid string" in error['msg'] and error['loc'] == ["XactActivityUSA"]
        for error in error_details
    ), "Expected validation error for 'XactActivityUSA' not found"


@pytest.mark.asyncio
@patch(
    target='backend.app.s3.file_ops.write_json_file'
)
@patch(
    target='backend.app.s3.file_ops.get_file_name_s3_folder'
)
@patch(
    target='backend.app.s3.file_ops.get_json_from_s3'
)
@patch(
    target='backend.app.s3.file_ops.update_backup'
)
async def test_update_damage_json_exist(backup_file, get_json, get_name_json, put_json,
                                        client: AsyncClient):
    damage_type = "backend_test"

    backup_file.return_value = {
        "message": "Successfully copied"
    }

    get_json.side_effect = [
        [
            {
                'XactCAT': 'Test',
                'XactSelUSA': 'TES',
                'XactDescriptionUSA': 'Accessories - Test',
                'XactActivityUSA': '+',
                'XactUnitUSA': 'US',
                'XactCategoryName': 'Accessories - Test',
                'Id': 'b7f0992bd071ae4fc2874872aa32860331248ef2063c3e3565864a642e853b42'
            },
            {
                'XactCAT': 'PREAF',
                'XactSelUSA': 'LASOR',
                'XactDescriptionUSA': 'Accessories - Test',
                'XactActivityUSA': '-',
                'XactUnitUSA': 'US',
                'XactCategoryName': 'Accessories - Test',
                'Id': '8f302e9c609f4a6296ba331a7441832844771e2060d51299f84fd358085a3a92'
            }
        ],
        [
            {
                'XactCAT': 'PREAF',
                'XactSelUSA': 'LASOR',
                'XactDescriptionUSA': 'Accessories - Test',
                'XactActivityUSA': '-',
                'XactUnitUSA': 'US',
                'XactCategoryName': 'Accessories - Test',
                'Id': '8f302e9c609f4a6296ba331a7441832844771e2060d51299f84fd358085a3a92'
            },
            {
                'XactCAT': 'SEL',
                'XactSelUSA': 'TES',
                'XactDescriptionUSA': 'Accessories - Test',
                'XactActivityUSA': '+',
                'XactUnitUSA': 'US',
                'XactCategoryName': 'Accessories - Test',
                'Id': 'b7dfg92bd071ae4fc2874872aa32860331248ef2063c3e3565864a642e853b42'
            }
        ],
        [
            {
                'XactCAT': 'PREAF',
                'XactSelUSA': 'LASOR',
                'XactDescriptionUSA': 'Accessories - Test',
                'XactActivityUSA': '-',
                'XactUnitUSA': 'US',
                'XactCategoryName': 'Accessories - Test',
                'Id': '8f302e9c609f4a6296ba331a7441832844771e2060d51299f84fd358085a3a92'
            },
            {
                'XactCAT': 'SELASDA',
                'XactSelUSA': 'TESFSDF',
                'XactDescriptionUSA': 'Accessories - Test',
                'XactActivityUSA': '+',
                'XactUnitUSA': 'US',
                'XactCategoryName': 'Accessories - Test',
                'Id': 'b7df392bd07asdw4fc2874872aa32860331248ef2063c3e3565864a642e853b42'
            }
        ]
    ]

    get_name_json.return_value = [
        "test_backend/test_backend.json",
        "test_backend/group/backend_group_test",
        "test_backend/subtype/backend_subtype_test"
    ]

    put_json.side_effect = [
        {
            "message": "File updated successfully"
        },
        {
            "message": "File updated successfully"
        },
        {
            "message": "File updated successfully"
        }
    ]

    response_put = client.put(
        url=f"orders/update_damage_file/",
        json={
            "damage_type": "test_backend",
            "data_json": [
                {
                    "XactActivityUSA": "+",
                    "XactCAT": "Test",
                    "XactCategoryName": "Accessories - Test",
                    "XactDescriptionUSA": "Accessories - Test",
                    "XactSelUSA": "TES",
                    "XactUnitUSA": "US"
                },
                {
                    "XactActivityUSA": "-",
                    "XactCAT": "REAL",
                    "XactCategoryName": "Accessories - Test",
                    "XactDescriptionUSA": "Accessories - Test",
                    "XactSelUSA": "LAS",
                    "XactUnitUSA": "US"
                }
            ]
        }
    )

    first_call_args, first_call_kwargs = put_json.call_args_list[0]
    second_call_args, second_call_kwargs = put_json.call_args_list[1]
    third_call_args, third_call_kwargs = put_json.call_args_list[2]

    expected_json_first_call = [
        {
            'XactCAT': 'SEL',
            'XactSelUSA': 'TES',
            'XactDescriptionUSA': 'Accessories - Test',
            'XactActivityUSA': '+',
            'XactUnitUSA': 'US',
            'XactCategoryName': 'Accessories - Test',
            'Id': 'b7dfg92bd071ae4fc2874872aa32860331248ef2063c3e3565864a642e853b42'
        }
    ]
    assert first_call_args[0] == expected_json_first_call

    expected_json_second_call = [
        {
            'XactCAT': 'SELASDA',
            'XactSelUSA': 'TESFSDF',
            'XactDescriptionUSA': 'Accessories - Test',
            'XactActivityUSA': '+',
            'XactUnitUSA': 'US',
            'XactCategoryName': 'Accessories - Test',
            'Id': 'b7df392bd07asdw4fc2874872aa32860331248ef2063c3e3565864a642e853b42'
        }
    ]
    assert second_call_args[0] == expected_json_second_call

    expected_json_third_call = [
        {
            'XactCAT': 'Test',
            'XactSelUSA': 'TES',
            'XactDescriptionUSA': 'Accessories - Test',
            'XactActivityUSA': '+',
            'XactUnitUSA': 'US',
            'XactCategoryName': 'Accessories - Test',
            'Id': 'b7f0992bd071ae4fc2874872aa32860331248ef2063c3e3565864a642e853b42'
        },
        {
            'XactCAT': 'REAL',
            'XactSelUSA': 'LAS',
            'XactDescriptionUSA': 'Accessories - Test',
            'XactActivityUSA': '-',
            'XactUnitUSA': 'US',
            'XactCategoryName': 'Accessories - Test',
            'Id': '8f302e9b209f4a6296ba331a7441832844771e2060d51299f84fd358085a3a92'
        }
    ]

    assert third_call_args[0] == expected_json_third_call

    assert response_put.status_code == 200
    response_data = response_put.json()
    assert response_data["message"] == "Updated successfully damage file"


@pytest.mark.asyncio
@patch(
    target="backend.app.routers.order.update_json_file"
)
async def test_update_list_damage_file(put_json, client: AsyncClient):
    put_json.return_value = {
        "message": "File updated successfully"
    }

    response_put = client.put(
        url="orders/update_damage_file/",
        json={
            "list_damage_json":
                {
                    'detail': 'Data',
                    'types': ['water', 'fire'],
                    'test': 'new_test_data'
                }
        }
    )

    assert response_put.status_code == 200
    response_data = response_put.json()
    assert response_data["message"] == "File updated successfully"


@pytest.mark.asyncio
async def test_update_damage_without_damage_type(client: AsyncClient):
    response_put = client.put(
        url="orders/update_damage_file/",
        json={
            "data_json":
                [
                    {
                        'XactCAT': 'Test',
                        'XactSelUSA': 'TES',
                        'XactDescriptionUSA': 'Accessories - Test',
                        'XactActivityUSA': '+',
                        'XactUnitUSA': 'US',
                        'XactCategoryName': 'Accessories - Test',
                    }
                ]
        }
    )

    assert response_put.status_code == 400
    response_data = response_put.json()
    assert response_data["detail"] == "damage_type is required"


@pytest.mark.asyncio
async def test_update_damage_without_parameters(client: AsyncClient):
    response_put = client.put(
        url="orders/update_damage_file/",
        json={}
    )

    assert response_put.status_code == 400
    response_data = response_put.json()
    assert response_data["detail"] == "At least one of 'damage_type' or 'list_damage_json' is required"


@pytest.mark.asyncio
async def test_update_damage_file_invalid_combination(client: AsyncClient):
    response_put = client.put(
        url="orders/update_damage_file/",
        json={
            "damage_type": "super",
            "list_damage_json":
                {
                    'detail': 'Data',
                    'types': ['water', 'fire'],
                    'test': 'new_test_data'
                }
        }
    )

    assert response_put.status_code == 400
    response_data = response_put.json()
    assert response_data["detail"] == "Invalid combination of request parameters"


@pytest.mark.asyncio
@patch(
    target="backend.app.s3.file_ops.delete_json_file"
)
@patch(
    target="backend.app.s3.file_ops.set_new_file_name"
)
@patch(
    target="backend.app.s3.file_ops.get_file_name_s3_folder"
)
async def test_update_name_damage_file(put_name_damage, set_name,
                                       delete_json, client: AsyncClient):
    put_name_damage.return_value = [
        "backend_test/backend_test.json",
        "backend_test/subtype/backend_subtype_test.json",
        "backend_test/group/backend_test_group.json"
    ]

    set_name.return_value = \
        {
            "message": "Files name updated successfully"
        }

    delete_json.return_value = {
        "message": "File deleted successfully"
    }

    response_put = client.put(
        url="orders/update_name_damage_file",
        json={
            "damage_type": "backend_test",
            "new_damage_type": "new_backend_test"
        }
    )

    first_call_args, first_call_kwargs = set_name.call_args_list[0]
    second_call_args, second_call_kwargs = set_name.call_args_list[1]
    third_call_args, third_call_kwargs = set_name.call_args_list[2]
    fourth_call_args, fourth_call_kwargs = set_name.call_args_list[3]

    expected_data_first_call = "backend_test/backend_test.json"
    assert first_call_args[0] == expected_data_first_call

    expected_data_second_call = "backend_test/subtype/backend_subtype_test.json"
    assert second_call_args[0] == expected_data_second_call

    expected_data_third_call = "backend_test/group/backend_test_group.json"
    assert third_call_args[0] == expected_data_third_call

    expected_data_fourth_call = "new_backend_test/backend_test.json"
    assert fourth_call_args[0] == expected_data_fourth_call

    first_call_args, first_call_kwargs = delete_json.call_args_list[0]
    second_call_args, second_call_kwargs = delete_json.call_args_list[1]
    third_call_args, third_call_kwargs = delete_json.call_args_list[2]
    fourth_call_args, fourth_call_kwargs = delete_json.call_args_list[3]

    expected_data_first_call = "backend_test/backend_test.json"
    assert first_call_args[0] == expected_data_first_call

    expected_data_second_call = "backend_test/subtype/backend_subtype_test.json"
    assert second_call_args[0] == expected_data_second_call

    expected_data_third_call = "backend_test/group/backend_test_group.json"
    assert third_call_args[0] == expected_data_third_call

    expected_data_fourth_call = "new_backend_test/backend_test.json"
    assert fourth_call_args[0] == expected_data_fourth_call

    assert response_put.status_code == 200
    response_data = response_put.json()
    assert response_data["message"] == "Successfully updated name damage_file"


@pytest.mark.asyncio
@patch(
    target="backend.app.s3.file_ops.delete_json_file"
)
@patch(
    target="backend.app.s3.file_ops.set_new_file_name"
)
async def test_update_name_subtype_damage_json(set_name, delete_json,
                                               client: AsyncClient):
    set_name.return_value = {
        "message": "Files name updated successfully"
    }

    delete_json.return_value = {
        "message": "File deleted successfully"
    }

    response_put = client.put(
        url="orders/update_name_damage_file",
        json={
            "damage_type": "backend_test",
            "substitution_type": "group",
            "old_substitution_name": "backend_test_group",
            "new_substitution_name": "new_backend_test_group"
        }
    )

    first_call_set_args, first_call_set_kwargs = set_name.call_args_list[0]
    first_call_delete_args, first_call_delete_kwargs = delete_json.call_args_list[0]

    expected_data_first_set_call = "backend_test/group/new_backend_test_group.json"
    assert first_call_set_args[1] == expected_data_first_set_call

    expected_data_first_delete_call = "backend_test/group/backend_test_group.json"
    assert first_call_delete_args[0] == expected_data_first_delete_call

    assert response_put.status_code == 200
    response_data = response_put.json()
    assert response_data["message"] == "Successfully updated name damage_file"


@pytest.mark.asyncio
@patch(
    target="backend.app.s3.file_ops.delete_objects"
)
@patch(
    target="backend.app.s3.file_ops.get_file_name_s3_folder"
)
async def test_delete_damage_json(get_file, delete_objects,
                                  client: AsyncClient):
    get_file.return_value = [
        "backend_test/backend_test.json",
        "backend_test/backend_substitution_test.json",
        "backend_test/group/new_backend_test_group.json"
    ]

    delete_objects.return_value = "Deleted successfully"
    damage_type = "backend_test"

    response_delete = client.delete(
        url=f"orders/delete_damage_json/{damage_type}"
    )

    first_call_args, first_call_kwargs = delete_objects.call_args_list[0]
    expected_data_first_set_call = {
        'Objects': [
            {'Key': "backend_test/backend_test.json"},
            {'Key': "backend_test/backend_substitution_test.json"},
            {'Key': "backend_test/group/new_backend_test_group.json"}
        ],
        'Quiet': False
    }

    assert first_call_kwargs['Delete'] == expected_data_first_set_call

    assert response_delete.status_code == 200
    response_data = response_delete.json()
    assert response_data["message"] == "File deleted successfully"


@pytest.mark.asyncio
@patch(
    target="backend.app.routers.order.delete_json_file"
)
async def test_delete_substitution_damage_json(delete_json, client: AsyncClient):
    delete_json.return_value = {
        "message": "File deleted successfully"
    }

    damage_type = "backend_test"

    response_delete = client.delete(
        url=f"orders/delete_damage_json/{damage_type}",
        params={
            "substitution_type": "group",
            "substitution_file_name": "backend_subtype_file"
        }
    )

    first_call_args, first_call_kwargs = delete_json.call_args_list[0]

    expected_data_first_call = "backend_test/group/backend_subtype_file.json"

    assert first_call_kwargs['s3_path'] == expected_data_first_call

    assert response_delete.status_code == 200
    response_data = response_delete.json()
    assert response_data["message"] == "File deleted successfully"


@pytest.mark.asyncio
@patch(
    target="backend.app.s3.file_ops.copy_object"
)
@patch(
    target="backend.app.s3.file_ops.get_file_name_s3_folder"
)
async def test_canceling_changes(get_file, copy, client):
    copy.return_value = "Successfully copied"
    get_file.return_value = [
        "temporary_backup/water/water.json",
        "temporary_backup/water/subtype/temporary_subtype.json",
        "temporary_backup/water/group/group_water.json"
    ]

    response = client.get(
        url="orders/canceling_changes/",
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["message"] == "Successful file rollback"


@pytest.mark.asyncio
@patch(
    target='backend.app.s3.file_ops.copy_object_in_s3'
)
async def test_put_order(copy_object, client: AsyncClient):
    copy_object.return_value = {
        "message": "Successfully copied"
    }

    response_put = client.put(
        url="orders/update_damage_file/",
        json={
            "damage_type": "test_backend",
            "substitution_type": "group",
            "substitution_json": {
                "json_substitution_name": "test_group_backend",
                "json_substitution_body": [
                    {
                        "XactActivityUSA": 1,
                        "XactCAT": "Test",
                        "XactCategoryName": "Accessories - Test",
                        "XactDescriptionUSA": "Accessories - Test",
                        "XactSelUSA": "TES",
                        "XactUnitUSA": "US"
                    },
                    {
                        "XactActivityUSA": "-",
                        "XactCAT": "REAL",
                        "XactCategoryName": "Accessories - Test",
                        "XactDescriptionUSA": "Accessories - Test",
                        "XactSelUSA": "LAS",
                        "XactUnitUSA": "US"
                    }
                ]
            }
        }
    )

    assert response_put.status_code == 200
    response_data = response_put.json()
    logger.info(f"{response_data}")
    assert response_data["detail"] == "There is not a single valid item in the received data"
