# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                               CraftForm                                      ║
# ╠══════════════════════════════════════════════════════════════════════════════╣
# ║  OPERATIONS LAMBDA  ::  regions.py                                           ║
# ║  The catalog of regions CraftForm is willing to deploy into.                 ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

# ==========================================================================================
#                                  REGION CATALOG
# ==========================================================================================
# this helps build the dictionary of supported regions and their friendly labels. based on
# the catalog file "regions.json" in this directory
# ------------------------------------------------------------------------------------------
import json
import os
from typing import Final

# captures the path to the catalog file based on this file's location
_CATALOG_PATH = os.path.join(os.path.dirname(__file__), "regions.json")

# capture the catalog into a dict for easy lookups by region code
with open(_CATALOG_PATH, encoding="utf-8") as catalog:
    _CATALOG: dict[str, str] = json.load(catalog)  # establish a dictionary from the json

# get just the codes
SUPPORTED: Final = frozenset(_CATALOG)


# =====================================FRIENDLY LABEL====================================
# get the pretty name for the region code, or just return the code if it's not already
# in the catalog (shouldn't happen but like yaknow a lot of things that shouldn't happen do)
def label(code: str) -> str:
    return _CATALOG.get(code, code)


# =====================================RESOLVE A REGION==================================
# label() backwards -- friendly name in, region code out.
def resolve(text: str | None) -> str | None:

    # `or ""` so a None gets handled here instead of blowing up on .strip()
    text = (text or "").strip().lower()

    if not text:
        return None

    # if already a code send back the code
    if text in _CATALOG:
        return text

    # check the catalog to get the region code
    for code, name in _CATALOG.items():
        if name.lower() == text:
            return code

    # if nothing worked :(
    return None
