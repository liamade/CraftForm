# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                               CraftForm                                      ║
# ╠══════════════════════════════════════════════════════════════════════════════╣
# ║  OPERATIONS LAMBDA  ::  responses.py                                         ║
# ║  Shared builders for the discord responses we send back through api gateway. ║
# ║  they just know discord's shapes, not ours                                   ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

# ==========================================================================================
#                            DISCORD INTERACTION RESPONSES
# ==========================================================================================
# every command ends by handing discord a json packet wrapped in the api gateway envelope.
# these build those packets so the command files don't have to repeat the boilerplate :)
# ------------------------------------------------------------------------------------------
import json
from typing import Any, TypedDict

# discord's ephemeral flag - only the person who ran the command sees the reply
EPHEMERAL = 64


class ApiResponse(TypedDict):
    statusCode: int
    headers: dict[str, str]
    body: str


# =================================API GATEWAY ENVELOPE==================================
# private - wraps a discord payload in the api gateway response shape. everything below
# goes through here so the envelope only lives in one place
def _respond(payload: dict[str, Any]) -> ApiResponse:
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload),
    }


# =======================================PONG===========================================
# type 1 = pong - discord's setup ping just wants a hello back :)
def pong() -> ApiResponse:
    return _respond({"type": 1})


# =====================================DEFERRED=========================================
# type 5 = deferred - shows the "thinking..." spinner and something follows up later
def deferred() -> ApiResponse:
    return _respond({"type": 5})


# ===================================PLAIN MESSAGE======================================
# type 4 = a plain ephemeral text reply for when there's nothing fancy to show
def plain_message(text: str) -> ApiResponse:
    # fmt: off
    return _respond({
        "type": 4,
        "data": {
            "content": text,
            "flags": EPHEMERAL,
        },
    })
    # fmt: on


# =======================================EMBED==========================================
# type 4 with one embed - the fancy card with a title, colour bar, footer and all that.
# the caller builds the embed dict, same deal as drop_down's options
def embed(embed: dict[str, Any]) -> ApiResponse:
    # fmt: off
    return _respond({
        "type": 4,
        "data": {
            "flags": EPHEMERAL,
            "embeds": [embed],
        },
    })
    # fmt: on


# =====================================DROP DOWN========================================
# type 4 with a string select menu. the caller builds the {"label", "value"} options so
# this stays dumb and doesn't have to know anything about regions or servers
def drop_down(content: str, custom_id: str, placeholder: str, options: list[dict[str, str]]) -> ApiResponse:
    # fmt: off
    return _respond({
        "type": 4,
        "data": {
            "content": content,
            "flags": EPHEMERAL,
            "components": [
                {
                    "type": 1,  # type 1 = action row (the box components sit in)
                    "components": [
                        {
                            "type": 3,  # type 3 = string select menu
                            "custom_id": custom_id,
                            "placeholder": placeholder,
                            "options": options,
                        }
                    ],
                }
            ],
        },
    })
    # fmt: on


# =======================================MODAL==========================================
# type 9 = modal (the pop-up form). the caller builds `fields` like this
#   {"custom_id": ..., "label": ..., "placeholder": ..., "value": ..., "required": bool}
#
# discord fails silently if you break these - a modal has to be the immediate response (no
# deferring first) and it's five fields max, one per action row :(
def modal(custom_id: str, title: str, fields: list[dict[str, Any]]) -> ApiResponse:
    # fmt: off
    return _respond({
        "type": 9,
        "data": {
            "custom_id": custom_id,
            "title": title,
            "components": [
                {
                    "type": 1,  # every text input gets its own action row
                    "components": [
                        {
                            "type": 4,   # type 4 = text input
                            "style": 1,  # style 1 = single line (2 would be a big paragraph box)
                            "custom_id": field["custom_id"],
                            "label": field["label"],
                            "placeholder": field.get("placeholder", ""),
                            "value": field.get("value", ""),
                            "required": field.get("required", True),
                        }
                    ],
                }for field in fields
            ],
        },
    })
    # fmt: on


# ====================================AUTOCOMPLETE======================================
# type 8 = the suggestion list while someone's still typing. `choices` is a list of
# {"name": shown, "value": sent} and it's 25 max or discord rejects the whole thing
def autocomplete(choices: list[dict[str, str]]) -> ApiResponse:
    # fmt: off
    return _respond({
        "type": 8,
        "data": {"choices": choices},
    })
    # fmt: on


# ==================================READ MODAL FIELDS===================================
# flattens a modal submit into {custom_id: value}. the values are buried one layer deeper
# than normal components because each input sits in its own action row
def modal_values(body: dict[str, Any]) -> dict[str, str]:
    return {row["components"][0]["custom_id"]: row["components"][0]["value"] for row in body["data"]["components"]}
