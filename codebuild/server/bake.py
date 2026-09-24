# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                               CraftForm                                      ║
# ╠══════════════════════════════════════════════════════════════════════════════╣
# ║  CODEBUILD  ::  bake.py                                                      ║
# ║  Bakes a minecraft server AMI from a per-type recipe.                        ║
# ║  Each type is a class with the same methods, so main stays type-blind.       ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

import json
import os
import time
import traceback

import boto3
import discord
from botocore.exceptions import WaiterError
from errors import BakeError

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

# =====================================PICK THE RECIPE======================================
# hands back the class already instantiated -- the constructor reads whatever env vars that
# type needs, so main just holds a recipe from here on
# ------------------------------------------------------------------------------------------
def pick_recipe(server_type):

    if server_type not in RECIPES:
        raise ValueError(f"'{server_type}' isn't a server type I know how to bake :(")

    return RECIPES[server_type]

# =====================================INSTANCE DETAILS=====================================
# the two things that change per-bake -- newest arm64 al2023, and a subnet in an az that
# actually offers the builder type today
# ------------------------------------------------------------------------------------------
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

# ====================================START THE INSTANCE====================================
# launches the builder and hands back its id -- the tags aren't decoration, SendCommand is
# scoped to Role=builder so it can't drive anything else
# ------------------------------------------------------------------------------------------
def start_instance(ec2,config, base_image, subnet):
    # launch the ec2
    response = ec2.run_instances(
        ImageId=base_image,
        InstanceType=BUILDER_TYPE,
        MinCount=1,
        MaxCount=1,
        SubnetId=subnet,
        SecurityGroupIds=[config["security_group"]],
        # the badge the agent needs to register -- borrowed off the region's server profile :)
        IamInstanceProfile={"Name": config["instance_profile"]},
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

# ====================================WAIT FOR THE AGENT====================================
# running just means the hardware's on -- the agent needs another minute to check in, and
# SendCommand throws InvalidInstanceId until it does. no boto3 waiter for this one :(
# ------------------------------------------------------------------------------------------
def wait_for_ssm(ssm, instance_id, timeout=300):

    deadline = time.time() + timeout

    while time.time() < deadline:

        # comes back empty until it registers -- that's the wait, not an error
        registered = ssm.describe_instance_information(
            Filters=[{"Key": "InstanceIds", "Values": [instance_id]}]
        )["InstanceInformationList"]

        if registered and registered[0]["PingStatus"] == "Online":
            print("Builder checked in with ssm :))")
            return

        time.sleep(10)

    raise BakeError("The builder never checked in with SSM, so the bake can't start :(")


def run_install(ssm, instance_id, commands):

    command_id = ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Parameters={
            "commands": commands,
        }
    )["Command"]["CommandId"]

    try:
        ssm.get_waiter("command_executed").wait(
            CommandId=command_id,
            InstanceId=instance_id,
            WaiterConfig={"Delay": 15, "MaxAttempts": 80},
        )


    except WaiterError:
        pass

    result = ssm.get_command_invocation(
        InstanceId=instance_id,
        CommandId=command_id,
    )

    print(f"install exit code: {result['ResponseCode']}")
    print(result['StandardOutputContent'])
    print(result['StandardErrorContent'])

    if result['ResponseCode'] != 0:
        raise BakeError(f"The build failed with {result['StandardOutputContent']} :(")

def build_template(ec2, instance_id, image_name) -> str:
    response = ec2.create_image(
        InstanceId=instance_id,
        Name=image_name,
        TagSpecifications=[
            {"ResourceType": "image", "Tags": [
                {"Key": "Project", "Value": "craftform"}
            ]},
            {"ResourceType": "snapshot", "Tags": [
                {"Key": "Project", "Value": "craftform"}
            ]}
        ]
    )

    return response['ImageId']

# ===========================================MAIN===========================================
# type-blind start to finish -- pick a recipe, resolve it, stand up a builder, bake on it
# ------------------------------------------------------------------------------------------
def main():

    # "flags" to check and see if the build succeeded
    instance_id = None
    image_id = None
    image_finished = False

    # both clients live in the DEPLOY region -- the agent checks in where the box lives,
    # so a home-region ssm client would never see the builder
    ec2 = boto3.client("ec2", region_name=os.environ["DEPLOY_REGION"])
    ssm = boto3.client("ssm", region_name=os.environ["DEPLOY_REGION"])

    try:
        # capture the server type used and get the class
        recipe = pick_recipe(os.environ["SERVER_TYPE"]).resolve()

        # check and make sure there isn't template already cached
        image_id = recipe.cache_check(ec2)

        if image_id is None:

            config = json.loads(os.environ["REGION_CONFIG"])

            # get the deployment details for the instance
            base_image, subnet = instance_details(ec2, config)

            # launch the ec2
            instance_id = start_instance(ec2, config, base_image, subnet)

            # wait for the hardware to come up -- blocks until it's running or raises WaiterError
            ec2.get_waiter("instance_running").wait(InstanceIds=[instance_id])

            # then wait for the agent inside it to actually check in with ssm
            wait_for_ssm(ssm, instance_id)

            # send the boot script
            run_install(ssm, instance_id, recipe.install_script())

            # create an ami template with the name
            image_id = build_template(ec2, instance_id, recipe.image_name())

            # wait for the instance ID to be complete
            ec2.get_waiter("image_available").wait(
                ImageIds=[image_id],
                WaiterConfig={"Delay": 15, "MaxAttempts": 40},
            )


        # flag to make sure it finished
        image_finished = True


        # get the details of the image and set a record in ssm/dynamo for it

        # write success

        # put the records into ssm/dynamodb


    except BakeError as e:
        discord.followup(str(e))
        raise


    except Exception:
        discord.followup("The build failed :(")
        traceback.print_exc()
        raise


    finally:
        if instance_id is not None:
            ec2.terminate_instances(
                InstanceIds = [instance_id]
            )

        if image_id and not image_finished:
            ec2.deregister_image(
                ImageId = image_id,
                DeleteAssociatedSnapshots = True
            )



if __name__ == "__main__":
    main()


