# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                               CraftForm                                      ║
# ╠══════════════════════════════════════════════════════════════════════════════╣
# ║  CODEBUILD  ::  bake.py                                                      ║
# ║  Bakes a minecraft server AMI from a per-type recipe.                        ║
# ║  Each type is a class with the same methods, so main stays type-blind.       ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

import os

import discord
from errors import BakeError
import boto3, json



# ==========================================================================================
#                                   THE RECIPE REGISTRY
# ==========================================================================================
# adding a type is one import and one line down here -- main never gets touched :)
# ------------------------------------------------------------------------------------------
from recipes.vanilla import Vanilla

# from recipes.modpack import Modpack
# from recipes.custom import Custom

RECIPES = {
    "vanilla": Vanilla,
    # "modpack": Modpack,
    # "custom":  Custom,
}
BUILDER_TYPE = "t4g.small"
BUILDER_TAGS = [
    {
        "Key": "Project",
        "Value": "craftform",
    },
    {
        "Key": "Role",
        "Value": "builder",
    }
]

# =====================================PICK THE RECIPE=====================================
# hands back the class already instantiated -- the constructor reads whatever env vars that
# type needs, so main just holds a recipe from here on
# ------------------------------------------------------------------------------------------
def pick_recipe(server_type):

    if server_type not in RECIPES:
        raise ValueError(f"'{server_type}' isn't a server type I know how to bake :(")

    return RECIPES[server_type]()

def instance_details(ec2, config):

    # capture the available images offered by amazon and have the specific name
    images = ec2.describe_images(
        Owners=["amazon"],
        Filters=[{"Name": "name", "Values": ["al2023-ami-2023.*-arm64"]}, {"Name": "state", "Values": ["available"]}],

    )['Images']
    # the base image used for the bake -- returns the biggest item by creation date
    base_image = max(images, key=lambda x: x["CreationDate"])["ImageId"]

    # get the subnet offered for right now
    offered_az = ec2.describe_instance_type_offerings(
        LocationType="availability-zone",
        Filters=[{"Name": "instance-type", "Values": [BUILDER_TYPE]}],
    )["InstanceTypeOfferings"]

    zones = {az["Location"] for az in offered_az}
    # the subnet used for the bake
    subnet = next((subnet for az, subnet in config["subnet_ids"].items() if az in zones), None)

    # make sure a subnet actually returned
    if subnet is None:
        raise BakeError("No subnet available for the bake :(")

    return base_image, subnet

def start_instance(ec2,config, base_image, subnet):
    # launch the ec2
    response = ec2.run_instances(
        ImageId=base_image,
        InstanceType=BUILDER_TYPE,
        MinCount=1,
        MaxCount=1,
        SubnetId=subnet,
        SecurityGroupIds=[config["security_group"]],
        TagSpecifications=[
            {
                "ResourceType": "instance",
                'Tags': BUILDER_TAGS
            },
            {
                "ResourceType": "volume",
                'Tags': BUILDER_TAGS
            }
        ]

    )

    # check the response back -- boto3 cancels the request if there's an error for me already so i don't have to check it
    print("Server created successfully :))")
    return response['Instances'][0]['InstanceId']

def main():

    try:
        # capture the server type used and get the class
        recipe = pick_recipe(os.environ["SERVER_TYPE"])

        # resolve the mc version and get the necessary info
        recipe.resolve()

        # create the ec2 client within the specified region
        ec2 = boto3.client("ec2", region_name=os.environ["DEPLOY_REGION"])
        config = json.loads(os.environ["REGION_CONFIG"])

        # get the deployment details for the instance
        base_image, subnet = instance_details(ec2, config)

        # launch the ec2
        instance_id = start_instance(ec2, config, base_image, subnet)

        # send the boot script






    except BakeError as e:
        discord.followup(str(e))
        raise

    except Exception:
        discord.followup(f"The bake for `{os.environ.get('SERVER_NAME', '?')}` fell over. :(")
        raise


if __name__ == "__main__":
    main()


