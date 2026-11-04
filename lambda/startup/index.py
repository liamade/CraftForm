# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                              CraftForm                                       ║
# ╠══════════════════════════════════════════════════════════════════════════════╣
# ║  STARTUP LAMBDA  ::  index.py                                                ║
# ║  Entry point for the CloudFormation Custom Resource startup function.        ║
# ║  Orchestrates the Discord setup on first deployment.                         ║
# ╚══════════════════════════════════════════════════════════════════════════════╝


# ==========================================================================================
#                            IMPORTS AND DEPENDENCIES
# ==========================================================================================
import json
import os  # for accessing environment variables injected into the Lambda
from typing import Any

import boto3
import urllib3
from discord_api import DiscordClient  # import the discord client class from discord_api

# ==========================================================================================
#                            SECRETS
# ==========================================================================================
# client lives at module scope so warm invocations reuse the same connection (AWS best practice).
# the Discord bot token is fetched at runtime and never stored in the function's env vars,
# so it doesn't show up in the Lambda config.
secrets_manager = boto3.client("secretsmanager")


def get_secrets() -> dict[str, str]:
    """Fetch and parse the craftform-secrets bundle from Secrets Manager."""
    secret = secrets_manager.get_secret_value(SecretId="craftform-secrets")
    return json.loads(secret["SecretString"])  # secret value is a JSON string


# both paths below need the same client -- app id is injected as an env var, bot token comes from Secrets Manager
def make_discord_client() -> DiscordClient:
    return DiscordClient(get_secrets()["Discord-Bot-Token"], os.environ["DiscordAppId"])


# ==========================================================================================
#                            MAIN LAMBDA FUNCTION ENTRY POINT
# ==========================================================================================


# context is lambda's runtime info object -- we never touch it, so `object` is all we promise.
# only the /update path returns anything -- cloudformation ignores the return and reads the PUT below
def handler(event: dict[str, Any], context: object) -> dict[str, str] | None:

    # ===============================RE-REGISTER COMMANDS ON UPDATE===============================
    # when someone runs /update, the staging function invokes this lambda to re-register commands
    if event.get("action") == "register_commands":
        # RUN
        try:
            make_discord_client().register_commands()  # registers whatever is in slash_commands now

        # ON FAILURE - this path ISN'T cloudformation, so there's no ResponseURL or StackId to hand back.
        except Exception as e:
            print(f"Failed to re-register commands: {e}")
            raise

        # ON SUCCESS
        return {"status": "commands registered :)"}  # staging only tells the user "done" once this comes back clean

    # ========================================STARTUP PATH========================================

    http = urllib3.PoolManager()  # init outside the try so the except/response path below can still reach it

    try:  # wrapping entire function in a try catch block because it makes it catches errors and also ensures when deleting cloudformation state, it deletes early
        # RUN -- make sure the startup script doesn't run on deletion
        if event["RequestType"] != "Delete":
            # =================================DISCORD INTEGRATION=============================
            discord_client = make_discord_client()

            discord_client.send_api_url(os.environ["ApiGatewayUrl"])  # set the API Gateway URL as the interactions endpoint in the Discord

            discord_client.register_commands()  # register the slash commands with the Discord API

        # =================================SUCCESS RESPONSE=============================
        outcome = {"Status": "SUCCESS"}

    # ====================================ERROR HANDLING================================
    # if any errors or failures happen - report to cloudformation with failure status and error message
    except Exception as e:
        outcome = {"Status": "FAILED", "Reason": str(e)}

    # =============================CLOUDFORMATION RESPONSE=============================
    # the bookkeeping fields are the same either way, so they get added once here
    # fmt: off
    response = {
        **outcome,
        "PhysicalResourceId": "craftform-startup",
        "StackId":            event["StackId"],
        "RequestId":          event["RequestId"],
        "LogicalResourceId":  event["LogicalResourceId"],
    }
    # fmt: on

    http.request(  # make an HTTP request to CloudFormation to report the end status
        "PUT",
        event["ResponseURL"],  # cloudformation response URL is given in the event object when the Lambda is invoked by CloudFormation
        body=json.dumps(response),  # success or failure, plus the bookkeeping fields
        headers={"Content-Type": "application/json"},
    )

    return None
