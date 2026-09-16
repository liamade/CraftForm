


import os, json, urllib3



class Vanilla:

    def __init__(self):
        self.server_type = os.environ["SERVER_TYPE"]

    # resolve the recipe's build parameters from the environment variables
    def resolve(self):
        # import env variables
        mc_version = os.environ["MC_VERSION"]

        # start the http client
        http = urllib3.PoolManager()

        # get the mc manifest and parse it
        manifest_url = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"

        manifest = http.request(
            "GET", 
            manifest_url
        )