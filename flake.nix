# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                               CraftForm                                    ║
# ╠══════════════════════════════════════════════════════════════════════════════╣
# ║  NIX  ::  flake.nix                                                        ║
# ║  The dev shell. every tool ci runs, pinned by flake.lock so it never drifts║
# ║  `direnv allow` once and it loads on cd. no direnv? `nix develop` works too║
# ╚══════════════════════════════════════════════════════════════════════════════╝
{
  description = "CraftForm -- discord-driven minecraft server infrastructure";

  inputs = {
    # unstable because checkov and terraform move fast and stable lags behind
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      # linux for this box and actions, darwin so a mac works too
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];

      # small flake-utils replacement, not worth another input for one function
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f (import nixpkgs {
        inherit system;

        config = {
          # terraform is BUSL now so nixpkgs calls it unfree. only allow terraform
          # instead of turning on allowUnfree for everything
          allowUnfreePredicate = pkg:
            builtins.elem (nixpkgs.lib.getName pkg) [ "terraform" ];

          # checkov pulls in ecdsa, which nixpkgs flags for CVE-2024-23342 (a timing
          # attack on signing). checkov never signs anything so it doesn't matter for us.
          # pinned to the exact version so a nixpkgs bump makes you look at this again
          permittedInsecurePackages = [ "python3.14-ecdsa-0.19.2" ];
        };
      }));
    in
    {
      # ======================================================================
      #                          THE EDITOR TOOLS
      # ======================================================================
      # pycharm has no direnv, so point its python at .venv/bin/python
      packages = forAllSystems (pkgs: {

        # `nix build .#dev-tools -o .dev-env` once and point the ide at .dev-env/bin
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
          # plain 3.12 to match the lambda and codebuild runtimes. uv.lock handles the packages
          python = pkgs.python312;

          # ====================================================================
          #                            THE CI RUNNER
          # ====================================================================
          # runs the same checks as ci-all.yaml so you find out before you push :)
          ci = pkgs.writeShellScriptBin "ci" ''
            # no -e on purpose so every check runs even if one fails
            set -uo pipefail

            ROOT="$(git rev-parse --show-toplevel)" || exit 1
            FAILED=()

            # sync like ci does (--locked fails on a stale uv.lock). add .venv to PATH
            # ourselves because `nix develop -c ci` skips direnv
            ( cd "$ROOT" && uv sync --locked --quiet ) || exit 1
            PATH="$ROOT/.venv/bin:$PATH"

            step() {
              # save the label before shift moves it
              local label="$1"; shift
              printf '\n\033[1;34m==> %s\033[0m\n' "$label"
              if "$@"; then
                printf '\033[0;32m    ok :)\033[0m\n'
              else
                printf '\033[0;31m    FAILED :(\033[0m\n'
                FAILED+=("$label")
              fi
            }

            # ---- cloudformation ----
            cfn() { cfn-lint "$ROOT"/cloudformation/*.yaml; }

            # ---- terraform ---- (subshells so the cd doesn't leak)
            tf_fmt()  { ( cd "$ROOT/terraform" && terraform fmt -check -recursive ); }
            tf_val()  { ( cd "$ROOT/terraform" \
                          && terraform init -backend=false -input=false >/dev/null \
                          && terraform validate ); }
            tf_lint() { ( cd "$ROOT/terraform" \
                          && tflint --init >/dev/null \
                          && tflint --recursive --format compact ); }

            # ---- python ---- (same as the lambda-ci.yaml matrix)
            # stops at the first failure in a package like ci does.
            # pytest exit 5 means no tests yet, so let it pass for now
            py() { ( cd "$ROOT/$1" \
                     && ruff format --diff . \
                     && ruff check . \
                     && mypy . \
                     && bandit -r . -ll \
                     && { pytest || [ $? -eq 5 ]; } ); }

            # ---- security ----
            # gitleaks 8.x renamed detect to git, so fall back for older versions
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
              pkgs.tflint     # config in terraform/.tflint.hcl
              pkgs.checkov    # config in .checkov.yaml

              # ================= PYTHON TOOLING ==============
              # uv is the only python tool from nix, the rest comes from uv.lock.
              # bump it with required-version in the root pyproject.toml
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

            # use the flake's 3.12 and never let uv download its own
            UV_PYTHON = "${python}/bin/python3.12";
            UV_PYTHON_DOWNLOADS = "never";

            shellHook = ''
              # checkov and awscli2 are built on python 3.14 and mkShell stacks their deps
              # onto PYTHONPATH, which breaks our 3.12 tools (cfn-lint dies on the wrong
              # build of regex). nothing here needs it so just drop it
              unset PYTHONPATH

              # always point uv at the repo root. otherwise `uv sync` inside a package strips
              # .venv down to just that package and you lose ruff and mypy.
              # to add a dep to one package run `uv add --package craftform-operations <dep>`
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
