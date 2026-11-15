import io
from concurrent.futures import ThreadPoolExecutor

import boto3
import pytest
from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import ClientError
from botocore.response import StreamingBody
from botocore.stub import Stubber

from boramae.store.local import LocalStore
from boramae.store.s3 import S3Store

PATH = "r/trend/0123456789abcdef0123456789abcdef.json"
CATALOG_PATH = "meta/catalog.json"
FIRST = b'{"a":1}'
SECOND = b'{"a":2}'
BUCKET = "boramae-test-data"
RACERS = 8


def stored_files(root) -> list[str]:
    return sorted(
        p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()
    )


def race_create_once(store: LocalStore, count: int) -> list[bool]:
    bodies = [f'{{"racer":{index}}}'.encode() for index in range(count)]
    with ThreadPoolExecutor(max_workers=count) as executor:
        return list(executor.map(lambda body: store.create_once(PATH, body), bodies))


def test_local_get_of_a_missing_path_returns_none(tmp_path):
    assert LocalStore(tmp_path).get(PATH) is None


def test_local_create_once_of_a_new_path_returns_true(tmp_path):
    assert LocalStore(tmp_path).create_once(PATH, FIRST) is True


def test_local_create_once_of_a_stored_path_returns_false(tmp_path):
    store = LocalStore(tmp_path)
    store.create_once(PATH, FIRST)
    assert store.create_once(PATH, SECOND) is False


def test_local_create_once_keeps_the_first_body(tmp_path):
    store = LocalStore(tmp_path)
    store.create_once(PATH, FIRST)
    store.create_once(PATH, SECOND)
    assert store.get(PATH) == FIRST


def test_local_create_once_leaves_only_the_result_file(tmp_path):
    LocalStore(tmp_path).create_once(PATH, FIRST)
    assert stored_files(tmp_path) == [PATH]


def test_local_racing_create_once_calls_create_one_file(tmp_path):
    assert race_create_once(LocalStore(tmp_path), RACERS).count(True) == 1


def test_local_put_leaves_only_the_catalog_file(tmp_path):
    LocalStore(tmp_path).put(CATALOG_PATH, FIRST)
    assert stored_files(tmp_path) == [CATALOG_PATH]


def test_local_put_replaces_the_body(tmp_path):
    store = LocalStore(tmp_path)
    store.put(CATALOG_PATH, FIRST)
    store.put(CATALOG_PATH, SECOND)
    assert store.get(CATALOG_PATH) == SECOND


def test_local_new_instance_reads_what_an_old_one_stored(tmp_path):
    LocalStore(tmp_path).create_once(PATH, FIRST)
    assert LocalStore(tmp_path).get(PATH) == FIRST


@pytest.fixture
def s3():
    client = boto3.client(
        "s3", region_name="us-west-2", config=Config(signature_version=UNSIGNED)
    )
    with Stubber(client) as stubber:
        yield S3Store(BUCKET, client), stubber


def conditional_put_params(body: bytes) -> dict[str, object]:
    return {
        "Bucket": BUCKET,
        "Key": PATH,
        "Body": body,
        "ContentType": "application/json",
        "IfNoneMatch": "*",
    }


def test_s3_create_once_sends_if_none_match_star(s3):
    store, stubber = s3
    stubber.add_response("put_object", {}, conditional_put_params(FIRST))
    assert store.create_once(PATH, FIRST) is True


def test_s3_create_once_reads_a_precondition_failure_as_exists(s3):
    store, stubber = s3
    stubber.add_client_error(
        "put_object",
        "PreconditionFailed",
        http_status_code=412,
        expected_params=conditional_put_params(FIRST),
    )
    assert store.create_once(PATH, FIRST) is False


def test_s3_create_once_reads_a_conditional_conflict_as_exists(s3):
    store, stubber = s3
    stubber.add_client_error(
        "put_object", "ConditionalRequestConflict", http_status_code=409
    )
    assert store.create_once(PATH, FIRST) is False


def test_s3_create_once_raises_any_other_error(s3):
    store, stubber = s3
    stubber.add_client_error("put_object", "AccessDenied", http_status_code=403)
    with pytest.raises(ClientError):
        store.create_once(PATH, FIRST)


def test_s3_get_returns_the_stored_body(s3):
    store, stubber = s3
    stubber.add_response(
        "get_object",
        {"Body": StreamingBody(io.BytesIO(FIRST), len(FIRST))},
        {"Bucket": BUCKET, "Key": PATH},
    )
    assert store.get(PATH) == FIRST


def test_s3_get_of_a_missing_key_returns_none(s3):
    store, stubber = s3
    stubber.add_client_error("get_object", "NoSuchKey", http_status_code=404)
    assert store.get(PATH) is None


def test_s3_get_raises_any_other_error(s3):
    store, stubber = s3
    stubber.add_client_error("get_object", "AccessDenied", http_status_code=403)
    with pytest.raises(ClientError):
        store.get(PATH)


def test_s3_put_sends_no_condition(s3):
    store, stubber = s3
    stubber.add_response(
        "put_object",
        {},
        {
            "Bucket": BUCKET,
            "Key": CATALOG_PATH,
            "Body": FIRST,
            "ContentType": "application/json",
        },
    )
    store.put(CATALOG_PATH, FIRST)
    stubber.assert_no_pending_responses()
