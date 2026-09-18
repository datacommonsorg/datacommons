# Creating a New DCP Testbed

> **One-time bootstrap.** Only needed when adding a brand-new testbed. To use an
> existing one, see [README.md](./README.md).

`fetch_terraform_state.sh` only **connects** to testbeds that already exist — it
has no `create` command, and `push-config` refuses to create a missing secret
("*Please ensure the testbed secret has been initialized by an administrator*").
Provisioning is done with the Data Commons CLI.

Prerequisites: `gcloud` authenticated against `datcom-dcp`, Terraform `>= 1.5.0`,
and a DC API key from <https://apikeys.datacommons.org>.

```bash
# 1. Scaffold inside the testbed workspaces directory (also prompts to create GCS remote state bucket if missing):
mkdir -p tests/testbed/workspaces
cd tests/testbed/workspaces

uv run datacommons admin init \
  --project-id datcom-dcp \
  --instance-name testbed-3 \
  --dc-api-key "YOUR_DC_API_KEY"

# Move into the scaffolded instance workspace:
cd testbed-3

# 2. Add the datcom-dcp-specific overrides BEFORE applying:
cat ../../testbed_overrides.tfvars.template >> terraform.tfvars

# 3. Apply. Check the plan names every resource <instance>-*, not another testbed's:
terraform plan
terraform apply

# 4. Register for the team so others can `connect`:
gcloud secrets create dcp-testbed-3-tfvars \
  --project=datcom-dcp --replication-policy=automatic
gcloud secrets versions add dcp-testbed-3-tfvars \
  --project=datcom-dcp --data-file=terraform.tfvars
```

> [!WARNING]
> Step 2 is not optional. The upstream template sets
> `spanner_create_bigquery_reservation = true`, but only one reservation may
> exist per project per region and `datcom-dcp` already has one. Skipping the
> overrides fails the apply partway and leaves a half-built testbed to clean up.
> See the template's comments for the rest of the rationale.

> [!NOTE]
> `--tf-git-ref` defaults to the tag matching the **CLI's own version**, not your
> local checkout. To bootstrap from an unreleased branch, pass `--tf-git-ref main`.

## Gotcha: branch skew in existing workspaces

When using local modules, `connect` copies `infra/dcp/*.tf` into the workspace but symlinks `modules/`. Switching git branches changes the modules underneath you while the root `.tf` files stay stale, producing confusing "unsupported argument" errors.

**Solution:**
* Run `./tests/testbed/fetch_terraform_state.sh configure --terraform-source git --terraform-ref <tag>` to hermetically pin Terraform modules directly from GitHub, eliminating branch skew.
* If testing local changes across branches, re-run `./tests/testbed/fetch_terraform_state.sh configure --terraform-source local` to refresh root `.tf` files.
