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
# aws_clients.py builds its boto3 clients the second it's imported and boto3 won't do that
# without a region. conftest runs before any test imports the lambda code so this gets in early.
# fake keys too so a test can never touch the real aws account :)
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ.pop("AWS_SESSION_TOKEN", None)
os.environ.pop("AWS_PROFILE", None)  # .envrc.local might set one -- don't let it win
