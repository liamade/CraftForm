# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                               CraftForm                                      ║
# ╠══════════════════════════════════════════════════════════════════════════════╣
# ║  STARTUP LAMBDA  ::  tests/conftest.py                                       ║
# ║  Shared test setup. pytest loads this file on its own, before any test.      ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
import os

# ==========================================================================================
#                                  FAKE AWS
# ==========================================================================================
# index.py builds its secrets manager client the MOMENT it's imported -- same deal as
# the operations lambda, see the note in lambda/operations/tests/conftest.py
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ.pop("AWS_SESSION_TOKEN", None)
os.environ.pop("AWS_PROFILE", None)  # .envrc.local might set one -- don't let it win
