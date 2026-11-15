import pytest

from boramae import constants


@pytest.mark.parametrize(
    ("ids", "expected"),
    [
        (constants.METRIC_IDS, 18),
        (constants.VARIABLE_IDS, 20),
        (constants.INTENT_IDS, 9),
    ],
    ids=["metrics", "variables", "intents"],
)
def test_id_list_holds_the_expected_number_of_unique_ids(ids, expected):
    assert len(set(ids)) == len(ids) == expected
