from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Self

import urllib3
from errors import BakeError

# stub-only package -- pip'd for ci, NOT in codebuild, so it can only be imported for mypy
if TYPE_CHECKING:
    from mypy_boto3_ec2 import EC2Client

# the mc api to resolve versions and get server data
MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"


# both mojang calls fail the same two ways, so they share one fetch. `what` names the thing
# we were after, so the error still says WHICH call broke
def _fetch_json(http: urllib3.PoolManager, url: str, what: str) -> Any:
    try:
        response = http.request("GET", url)
    except urllib3.exceptions.HTTPError as e:
        raise BakeError(f"Couldn't reach Mojang for {what}.") from e

    if response.status != 200:
        raise BakeError(f"Mojang came back with an error {response.status} for {what}. :(")

    return response.json()


class Vanilla:
    def __init__(self, mc_version: str, jar_url: str, jar_sha1: str, java_version: int) -> None:
        self.server_type = os.environ["SERVER_TYPE"]

        # mc details
        self.mc_version = mc_version
        self.jar_url = jar_url
        self.jar_sha1 = jar_sha1
        self.java_version = java_version  # mojang's majorVersion -- a plain int like 21

    # resolve the recipe's build parameters from the environment variables
    @classmethod
    def resolve(cls) -> Self:

        http = urllib3.PoolManager(timeout=10)

        # import env variables
        mc_version = os.environ["MC_VERSION"]

        # get the big boy manifest
        data = _fetch_json(http, MANIFEST_URL, "the version list")

        # capture tha actual version latest is
        if mc_version == "latest":
            mc_version = data["latest"]["release"]

        # capture the version object
        version = next((v for v in data["versions"] if v["id"] == mc_version), None)
        if version is None:
            raise BakeError(f"'{mc_version}' isn't a minecraft version mojang knows about")

        # make a request on the exact version to get the server jar and java version
        version_data = _fetch_json(http, version["url"], f"the {mc_version} details")

        # make sure the results exist
        if "server" not in version_data["downloads"]:
            raise BakeError(f"Minecraft {mc_version} has no server download.")
        if "javaVersion" not in version_data:
            raise BakeError(f"Mojang doesn't list a Java version for {mc_version}.")

        # capture the results
        return cls(
            mc_version=version_data["id"],
            jar_url=version_data["downloads"]["server"]["url"],
            jar_sha1=version_data["downloads"]["server"]["sha1"],
            java_version=version_data["javaVersion"]["majorVersion"],
        )

    def cache_check(self, ec2: EC2Client) -> str | None:
        images = ec2.describe_images(
            Owners=["self"],
            Filters=[
                {"Name": "name", "Values": [self.image_name()]},
                {"Name": "state", "Values": ["available"]},
            ],
        )["Images"]

        return images[0]["ImageId"] if images else None

    def install_script(self) -> list[str]:
        return [
            "set -euo pipefail",
            f"dnf install -y java-{self.java_version}-amazon-corretto-headless",
            "mkdir -p /opt/minecraft",
            "cd /opt/minecraft",
            f"curl -fsSL -o server.jar {self.jar_url}",
            f'echo "{self.jar_sha1}  server.jar" | sha1sum -c -',
            'echo "eula=true" > eula.txt',
            "dnf clean all",
        ]

    def image_name(self) -> str:
        return f"craftform-vanilla-{self.mc_version}"
