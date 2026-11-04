import json
import os

import urllib3

http = urllib3.PoolManager(timeout=10)

FOLLOWUP_URL = "https://discord.com/api/v10/webhooks/{app_id}/{token}/messages/@original"


# edit the "thinking..." message the operations lambda deferred. returns False instead of
# raising -- a report that can't reach discord shouldn't hide the bake's real error
def followup(text: str) -> bool:
    try:
        url = FOLLOWUP_URL.format(
            app_id=os.environ["DISCORD_APP_ID"],
            token=os.environ["DISCORD_TOKEN"],
        )

        response = http.request(
            "PATCH",
            url,
            headers={"Content-Type": "application/json"},
            body=json.dumps({"content": text}),
        )

    except Exception as e:
        print(f"Couldn't reach discord to report back: {e} :(")
        return False

    if response.status != 200:
        print(f"Discord rejected the followup: {response.status} - {response.data.decode()} :(")
        return False

    return True
