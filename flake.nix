# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                               CraftForm                                      ║
# ╠══════════════════════════════════════════════════════════════════════════════╣
# ║  NIX  ::  flake.nix                                                          ║
# ║  The dev shell - every tool ci runs, pinned by flake.lock so it never drifts ║
# ║  `direnv allow` once and it just loads on cd. no direnv? `nix develop` :)    ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
{
  description = "CraftForm -- discord-driven minecraft server infrastructure";

  inputs = {
    # unstable because checkov and terraform move fast and stable just can't keep up
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      # linux for my box and actions, darwin so mac people can join in too
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];

      # a tiny flake-utils so we don't need a whole other input for one function
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f (import nixpkgs {
        inherit system;

        config = {
          # terraform went BUSL so nixpkgs calls it unfree and won't build it - we only let
          # terraform through instead of allowing every unfree thing
          allowUnfreePredicate = pkg:
            builtins.elem (nixpkgs.lib.getName pkg) [ "terraform" ];

          # checkov pulls in ecdsa and nixpkgs is scared of CVE-2024-23342 (a timing attack
          # on signing). checkov never signs anything so we're good.
          # pinned to the exact version so a nixpkgs bump breaks this and makes me look again
          permittedInsecurePackages = [ "python3.14-ecdsa-0.19.2" ];
        };
      }));
    in
    {
      # ======================================================================
      #                          THE EDITOR TOOLS
      # ======================================================================
      # pycharm doesn't do direnv so just point it at .venv/bin/python
      packages = forAllSystems (pkgs: {

        # run `nix build .#dev-tools -o .dev-env` once and point the ide at .dev-env/bin
        dev-tools = pkgs.symlinkJoin {
          name = "craftform-dev-tools";
          paths = [ pkgs.terraform ];
        };
      });

      devShells = forAllSystems (pkgs:
        let
          # ====================================================================
          #                              PYTHON
          # ====================================================================
          # just plain 3.12 to match lambda and codebuild - uv.lock handles the packages
          python = pkgs.python312;

          # ====================================================================
          #                            THE CI RUNNER
          # ====================================================================
          # runs the same checks as ci-all.yaml so you find out here instead of three minutes into a pushed run :)
          ci = pkgs.writeShellScriptBin "ci" ''
            # no -e so every check still runs even if one fails and you get the whole picture
            set -uo pipefail

            ROOT="$(git rev-parse --show-toplevel)" || exit 1
            FAILED=()

            # sync the venv like ci does (--locked fails if uv.lock is stale) and add it to PATH
            # ourselves since `nix develop -c ci` skips direnv
            ( cd "$ROOT" && uv sync --locked --quiet ) || exit 1
            PATH="$ROOT/.venv/bin:$PATH"

            step() {
              # grab the label before shift eats it
              local label="$1"; shift
              printf '\n\033[1;34m==> %s\033[0m\n' "$label"
              if "$@"; then
                printf '\033[0;32m    ok :)\033[0m\n'
              else
                printf '\033[0;31m    FAILED :(\033[0m\n'
                FAILED+=("$label")
              fi
            }

            # CLOUDFORMATION
            cfn() { cfn-lint "$ROOT"/cloudformation/*.yaml; }

            # TERRAFORM - subshells so the cd doesn't leak into the next step
            tf_fmt()  { ( cd "$ROOT/terraform" && terraform fmt -check -recursive ); }
            tf_val()  { ( cd "$ROOT/terraform" \
                          && terraform init -backend=false -input=false >/dev/null \
                          && terraform validate ); }
            tf_lint() { ( cd "$ROOT/terraform" \
                          && tflint --init >/dev/null \
                          && tflint --recursive --format compact ); }

            # PYTHON - same as the lambda-ci.yaml matrix
            # stops at the first failure in a package like ci does.
            # pytest exit 5 means there's no tests yet so just let it pass for now
            py() { ( cd "$ROOT/$1" \
                     && ruff format --diff . \
                     && ruff check . \
                     && mypy . \
                     && bandit -r . -ll \
                     && { pytest || [ $? -eq 5 ]; } ); }

            # SECURITY - gitleaks 8.x renamed detect to git so fall back if it's an older one
            leaks() {
              if gitleaks git --help >/dev/null 2>&1; then
                gitleaks git "$ROOT" --no-banner
              else
                gitleaks detect --source "$ROOT" --no-banner
              fi
            }
            iac() { ( cd "$ROOT" && checkov --config-file .checkov.yaml ); }

            step "cloudformation lint"  cfn
            step "terraform fmt"        tf_fmt
            step "terraform validate"   tf_val
            step "tflint"               tf_lint
            step "lambda: startup"      py lambda/startup
            step "lambda: operations"   py lambda/operations
            step "codebuild: server"    py codebuild/server
            step "gitleaks"             leaks
            step "checkov"              iac

            echo ""
            if [ ''${#FAILED[@]} -eq 0 ]; then
              printf '\033[0;32mall checks passed :)\033[0m\n'
            else
              printf '\033[0;31m%s check(s) failed:\033[0m %s\n' "''${#FAILED[@]}" "''${FAILED[*]}"
              exit 1
            fi
          '';
        in
        {
          default = pkgs.mkShell {
            name = "craftform";

            packages = [
              python
              ci

              # ==================== IAC ====================
              pkgs.terraform  # buildspec.yaml pins its own copy
              pkgs.tflint     # config lives in terraform/.tflint.hcl
              pkgs.checkov    # config lives in .checkov.yaml

              # ================= PYTHON TOOLING ==============
              # uv is the only python thing we grab from nix, everything else comes from uv.lock.
              # bump it with required-version in the root pyproject.toml or uv gets mad
              pkgs.uv         # 0.12.5 right now

              # ================ EDITOR SUPPORT ===============
              # the vscode nix extension needs these for completions and jump to definition
              pkgs.nixd       # nix language server
              pkgs.nixfmt     # nix formatter

              # ================ EVERYTHING ELSE ==============
              pkgs.gitleaks   # the secret scan ci runs
              pkgs.awscli2    # poking at the stack by hand
              pkgs.jq         # the buildspec builds its discord json with this
              pkgs.zip        # for testing the release zips locally
              pkgs.unzip
            ];

            # use the flake's 3.12 and never let uv go download its own
            UV_PYTHON = "${python}/bin/python3.12";
            UV_PYTHON_DOWNLOADS = "never";

            shellHook = ''
              # checkov and awscli2 are built on python 3.14 and mkShell dumps all their deps onto
              # PYTHONPATH, which breaks our 3.12 tools. cfn-lint grabs the 3.14 regex and just dies :(
              # nothing here needs PYTHONPATH anyway so we just drop it
              unset PYTHONPATH

              # always point uv at the repo root. otherwise `uv sync` inside a package strips .venv
              # down to just that package and you lose ruff and mypy :(
              # adding a dep to one package is `uv add --package craftform-operations <dep>`
              export UV_PROJECT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

              echo ""
              echo "  CraftForm  ::  dev shell"
              echo "  ---------------------------------------------"
              echo "  ci    run every check ci-all.yaml runs"
              echo ""
              echo "  no direnv? run: uv sync && source .venv/bin/activate"
              echo ""
            '';
          };
        });
    };
}
