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


# =====================================PICK THE RECIPE=====================================
# hands back the class already instantiated -- the constructor reads whatever env vars that
# type needs, so main just holds a recipe from here on
# ------------------------------------------------------------------------------------------
def pick_recipe(server_type):

    if server_type not in RECIPES:
        raise ValueError(f"'{server_type}' isn't a server type I know how to bake :(")

    return RECIPES[server_type]()


def main():

    try:
        # capture the server type used and get the class
        recipe = pick_recipe(os.environ["SERVER_TYPE"])

        # resolve the mc version and get the necessary info
        recipe.resolve()

    except BakeError as e:
        discord.followup(str(e))
        raise

    except Exception:
        discord.followup(f"The bake for `{os.environ.get('SERVER_NAME', '?')}` fell over. :(")
        raise


if __name__ == "__main__":
    main()


