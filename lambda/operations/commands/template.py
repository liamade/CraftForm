# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                               CraftForm                                      ║
# ╠══════════════════════════════════════════════════════════════════════════════╣
# ║  OPERATIONS LAMBDA  ::  commands/template.py                                 ║
# ║  Handles all /template slash command interactions.                           ║
# ║  Create, delete, list, and modify templates.                                 ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
from typing import Any

import responses  # discord interaction-response builders


# ==========================================================================================
#                                  /TEMPLATE COMMAND
# ==========================================================================================
def handle(subcommand: str, options: list[dict[str, Any]], body: dict[str, Any]) -> responses.ApiResponse:

    # --------------------------------CREATE--------------------------------
    if subcommand == "create":
        pass

    # --------------------------------DELETE--------------------------------
    if subcommand == "delete":
        pass

    # --------------------------------LIST--------------------------------
    if subcommand == "list":
        pass

    # --------------------------------MODIFY--------------------------------
    if subcommand == "modify":
        pass

    # every branch above is still a stub -- reply instead of handing api gateway a None
    return responses.plain_message(f"`/template {subcommand}` isn't built yet :(")
