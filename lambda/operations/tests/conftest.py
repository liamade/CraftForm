# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                               CraftForm                                      ║
# ╠══════════════════════════════════════════════════════════════════════════════╣
# ║  OPERATIONS LAMBDA  ::  tests/conftest.py                                    ║
# ║  Shared test setup. pytest loads this file on its own, before any test.      ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
import os

# ==========================================================================================
#                                  FAKE AWS
# ==========================================================================================
# aws_clients.py builds its boto3 clients the MOMENT it's imported, and boto3 refuses
# to do that without a region. this file runs before any test imports the lambda code,
# so setting these here (not inside a test) is what gets them in early enough.
#
# the fake keys also mean a test can never actually do anything to your real aws
# account -- any call that slips through just fails with bad credentials
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ.pop("AWS_SESSION_TOKEN", None)
os.environ.pop("AWS_PROFILE", None)  # .envrc.local might set one -- don't let it win
