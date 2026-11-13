import json
from typing import Any

from responses import ApiResponse, autocomplete, deferred, drop_down, embed, modal, modal_values, plain_message, pong

# discord's ephemeral flag, typed straight from their docs
EPHEMERAL_FLAG = 64


# open the envelope -- body is a json string, turn it back into a dict to check it
def body_of(response: ApiResponse) -> dict[str, Any]:
    return json.loads(response["body"])


def test_pong():
    response = pong()

    assert response["statusCode"] == 200
    assert response["headers"]["Content-Type"] == "application/json"
    assert body_of(response) == {"type": 1}


def test_deferred():

    response = deferred()

    assert body_of(response) == {"type": 5}


def test_plain_message():

    random_message = "stinky butt"

    response = plain_message(random_message)

    assert body_of(response) == {
        "type": 4,
        "data": {
            "content": random_message,
            "flags": EPHEMERAL_FLAG,
        },
    }


def test_embed():
    test_embed_dict = {
        "title": "Test Embed",
        "description": "This is a test embed",
    }

    response = embed(test_embed_dict)

    assert body_of(response) == {
        "type": 4,
        "data": {
            "embeds": [test_embed_dict],
            "flags": EPHEMERAL_FLAG,
        },
    }


def test_drop_down():

    test_content = "Test Drop Down"
    test_custom_id = "test_drop_down"
    test_placeholder = "Select an option"
    test_drop_down_options = [
        {"label": "Option 1", "value": "option_1"},
        {"label": "Option 2", "value": "option_2"},
    ]

    response = drop_down(test_content, test_custom_id, test_placeholder, test_drop_down_options)

    # drill in one layer at a time -- message -> action row -> select menu
    body = body_of(response)
    data = body["data"]
    row = data["components"][0]
    menu = row["components"][0]

    assert body["type"] == 4  # 4 = message reply
    assert data["content"] == test_content
    assert data["flags"] == EPHEMERAL_FLAG

    assert row["type"] == 1  # 1 = action row

    assert menu["type"] == 3  # 3 = string select menu
    assert menu["custom_id"] == test_custom_id
    assert menu["placeholder"] == test_placeholder
    assert menu["options"] == test_drop_down_options


def test_drop_down_empty_options():

    test_content = "Test Drop Down"
    test_custom_id = "test_drop_down"
    test_placeholder = "Select an option"
    test_drop_down_options: list[dict[str, str]] = []

    response = drop_down(test_content, test_custom_id, test_placeholder, test_drop_down_options)

    # drill in one layer at a time -- message -> action row -> select menu
    body = body_of(response)
    data = body["data"]
    row = data["components"][0]
    menu = row["components"][0]

    assert body["type"] == 4  # 4 = message reply
    assert data["content"] == test_content
    assert data["flags"] == EPHEMERAL_FLAG

    assert row["type"] == 1  # 1 = action row

    assert menu["type"] == 3  # 3 = string select menu
    assert menu["custom_id"] == test_custom_id
    assert menu["placeholder"] == test_placeholder
    assert menu["options"] == test_drop_down_options


def test_modal():

    test_custom_id = "test_modal"
    test_title = "Modal Title"
    # fields are what the CALLER passes -- modal() wraps each one in a row + text input.
    # these leave out placeholder/value/required on purpose, to check the defaults
    test_fields = [
        {"custom_id": "field_1", "label": "Field 1"},
        {"custom_id": "field_2", "label": "Field 2"},
    ]

    response = modal(test_custom_id, test_title, test_fields)

    # drill in one layer at a time -- modal -> rows (one per field) -> text input
    body = body_of(response)
    data = body["data"]
    rows = data["components"]

    assert body["type"] == 9  # 9 = modal
    assert data["custom_id"] == test_custom_id
    assert data["title"] == test_title
    assert len(rows) == len(test_fields)  # one row per field

    # same checks for every row, in the same order the fields went in
    for row, field in zip(rows, test_fields):
        text_input = row["components"][0]

        assert row["type"] == 1  # 1 = action row
        assert text_input["type"] == 4  # 4 = text input
        assert text_input["style"] == 1  # 1 = single line
        assert text_input["custom_id"] == field["custom_id"]
        assert text_input["label"] == field["label"]

        # the defaults, since the fields above didn't set these
        assert text_input["placeholder"] == ""
        assert text_input["value"] == ""
        assert text_input["required"] is True


def test_autocomplete():

    test_choices = [
        {"name": "Choice 1", "value": "choice_1"},
        {"name": "Choice 2", "value": "choice_2"},
    ]

    response = autocomplete(test_choices)

    body = body_of(response)
    assert body["data"]["choices"] == test_choices
    assert body["type"] == 8  # 8 = autocomplete


def test_modal_values():

    test_body = {
        "data": {
            "components": [
                {
                    "components": [
                        {"custom_id": "stuff", "value": "here"},
                    ],
                },
                {
                    "components": [
                        {"custom_id": "more_stuff", "value": "there"},
                    ],
                },
                {
                    "components": [
                        {"custom_id": "even_more_stuff", "value": "everywhere"},
                    ],
                },
            ],
        },
    }

    values = modal_values(test_body)

    assert values == {
        "stuff": "here",
        "more_stuff": "there",
        "even_more_stuff": "everywhere",
    }
