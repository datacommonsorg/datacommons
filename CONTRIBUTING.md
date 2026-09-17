# Contributing to the Data Commons Platform

The Data Commons Platform (DCP) welcomes contributions from developers, researchers, and data practitioners.

---

## Getting Started

* **New to DCP?** Start with the [Developer Onboarding Codelab](docs/codelabs/dcp_developer_onboarding.md) to set up and deploy a test instance.
* **Developer Guide & Codebase Layout**: Read the [Developer Guide](docs/developer_guide.md) for monorepo package details, local development recipes, and testing instructions.
* **Architecture & Data Flows**: Read [Platform Architecture](docs/architecture/platform_architecture.md) for an overview of the 4-repository topology, container artifacts, and data flows.

---

## Tooling Prerequisites

To build, test, and contribute, install the following tools:
* **Python (v3.11+)**: Required for core packages.
* **[uv](https://docs.astral.sh/uv/)**: Python project and package manager.
* **[Terraform](https://developer.hashicorp.com/terraform/install) (v1.5+)**: Required when modifying configurations in `infra/dcp/`.
* **[gcloud CLI](https://cloud.google.com/sdk/docs/install-sdk)**: Google Cloud SDK for project authentication.
* **[Docker](https://docs.docker.com/get-docker/)**: Required for running local hermetic integration tests with Docker Compose.

---

## Code Quality and Testing

All code contributions (features, fixes, and CLI subcommands) are expected to include unit tests. Before submitting a pull request, format your code, verify linting, and run the test suite:

### Formatting and Linting
Format and lint all Python packages using `ruff` via `uv`:
```bash
# Format code
uv run ruff format

# Check for lint errors
uv run ruff check
```

### Running Tests
Run unit tests across all packages:
```bash
uv run pytest
```

For emulated end-to-end integration tests using Docker Compose, refer to the [Integration Tests Guide](tests/integration/README.md):
```bash
uv run pytest tests/integration/suites/ \
    --instance emulated \
    --test-config foobar_wages
```

---

## Documentation Standards

When contributing documentation, follow the standards defined in [docs/README.md](docs/README.md):
* **Centralize in `docs/`**: Place architectural specifications in `docs/architecture/` and tutorials in `docs/codelabs/`.
* **Keep Local READMEs Operational**: Subsystem READMEs (such as [infra/dcp/README.md](infra/dcp/README.md) and [packages/datacommons-cli/README.md](packages/datacommons-cli/README.md)) focus strictly on operational commands, inputs, outputs, and variable references.
* **Persona Separation**: [docs/user_guide.md](docs/user_guide.md) serves DCP Admins. Keep developer workflows, workbench recipes, and codelabs in [docs/developer_guide.md](docs/developer_guide.md), `docs/codelabs/`, or `docs/architecture/`.

---

## Pull Request Guidelines

1. **Focused Changes**: Keep pull requests focused on a single feature or bug fix. Avoid bundling unrelated refactors or reformatting.
2. **Commit Messages**: Write clear, descriptive commit messages following the Conventional Commits format (for example, `feat(cli): ...`, `fix(terraform): ...`, `docs: ...`).
3. **Branch History**: Once a review begins, push incremental commits rather than force-pushing or rewriting git history so reviewers can inspect incremental changes.
4. **Documentation Updates**: If modifying variables, schemas, or CLI commands, update the corresponding documentation files.

---

## Contributor License Agreement & License

Contributions to this project must be accompanied by a Contributor License Agreement (CLA). If you or your organization have not signed the Google CLA, please sign at [https://cla.developers.google.com/](https://cla.developers.google.com/).

By contributing to Data Commons, you agree that your contributions will be licensed under the [Apache-2.0 License](LICENSE).
