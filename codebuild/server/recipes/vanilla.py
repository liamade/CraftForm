


import os

import urllib3
from errors import BakeError


class Vanilla:

    def __init__(self, mc_version: str, jar_url: str, jar_sha1: str, java_version: str):
        self.server_type = os.environ["SERVER_TYPE"]

        # mc details
        self.mc_version = mc_version
        self.jar_url = jar_url
        self.jar_sha1 = jar_sha1
        self.java_version = java_version

    # resolve the recipe's build parameters from the environment variables
    @classmethod
    def resolve(cls):

        http = urllib3.PoolManager(timeout=10)


        # import env variables
        mc_version = os.environ["MC_VERSION"]

        # the mc api to resolve versions and get server data
        manifest_url = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"

        # get the big boy manifest
        try:
            manifest = http.request(
                "GET",
                manifest_url
            )
        except urllib3.exceptions.HTTPError as e:
            raise BakeError("Couldn't reach Mojang for the version list.") from e

        if manifest.status != 200:
            raise BakeError(f"Mojang's version list came back with an error {manifest.status}. :(")

        # load the response as a json
        data = manifest.json()

        # capture tha actual version latest is
        if mc_version == "latest": mc_version = data["latest"]["release"]

        # capture the version object
        version = next((v for v in data["versions"] if v["id"] == mc_version), None)
        if version is None:
            raise BakeError(f"'{mc_version}' isn't a minecraft version mojang knows about")

        # make a request on the exact version to get the server jar and java version
        try:
            manifest = http.request(
                "GET",
                version["url"]
            )
        except urllib3.exceptions.HTTPError as e:
            raise BakeError(f"Couldn't reach Mojang for the {mc_version} details.") from e

        if manifest.status != 200:
            raise BakeError(f"Mojang's info for {mc_version} came back with an error {manifest.status}. :(")

        version_data = manifest.json()

        # make sure the results exist
        if "server" not in version_data["downloads"]: raise BakeError(f"Minecraft {mc_version} has no server download.")
        if "javaVersion" not in version_data: raise BakeError(f"Mojang doesn't list a Java version for {mc_version}.")

        # capture the results
        return cls(
            mc_version = version_data["id"],
            jar_url = version_data["downloads"]["server"]["url"],
            jar_sha1 = version_data["downloads"]["server"]["sha1"],
            java_version = version_data["javaVersion"]["majorVersion"]
        )

    def install_script(self) -> list[str]:
        return [
            "set -euo pipefail",
            f"dnf install -y java-{self.java_version}-amazon-corretto-headless",
            "mkdir -p /opt/minecraft",
            "cd /opt/minecraft",
            f"curl -fsSL -o server.jar {self.jar_url}",
            f'echo "{self.jar_sha1}  server.jar" | sha1sum -c -',
            'echo "eula=true" > eula.txt',
            'dnf clean all'
        ]


    def image_name(self) -> str:
        return f"craftform-vanilla-{self.mc_version}"



