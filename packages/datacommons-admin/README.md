# Data Commons Admin Tooling

<p align="center">
  <a href="https://www.datacommons.org"><img src="https://datacommons.org/images/dc-logo.svg" alt="Data Commons" width="120"></a>
</p>

<p align="center">
  <em>The administrative and deployment tooling of the Data Commons Platform.</em>
</p>

---

`datacommons-admin` provides administrative subcommands of the Data Commons Platform. It handles the heavy lifting for:
- Scaffolding and configuring Terraform templates.
- Provisioning GCP infrastructure (GCS Buckets, Spanner instance/databases).
- Managing and seeding platform schemas and geographic datasets.
- Directing background data ingestion pipelines on Cloud Run and Cloud Workflows.

---

> [!IMPORTANT]
> ### Looking for the Command Line Tool?
> This package is designed as a library module and is consumed by the main entrypoint CLI.
> 
> To execute administrative commands on your terminal, please download and install the main **[datacommons-cli](https://pypi.org/project/datacommons-cli/)** package:
> 
> ```bash
> pip install --user datacommons-cli
> # Or using uv
> uv tool install datacommons-cli
> ```
> Once installed, all administrative features from this package are exposed under:
> ```bash
> datacommons admin --help
> ```
>
> Alternatively, run the admin CLI without installing it using uvx:
> ```bash
> uvx datacommons-cli admin --help
> ```

---

## Links & Resources

- **Core CLI Package**: [datacommons-cli on PyPI](https://pypi.org/project/datacommons-cli/)
- **Source Code**: [datacommons-cli on GitHub](https://github.com/datacommonsorg/datacommons/tree/main/packages/datacommons-cli), [datacommons-admin on GitHub](https://github.com/datacommonsorg/datacommons/tree/main/packages/datacommons-admin)
- **Official Website**: [datacommons.org](https://www.datacommons.org)
- **Platform Documentation**: [docs.datacommons.org](https://docs.datacommons.org)

---

License: [Apache-2.0](https://github.com/datacommonsorg/datacommons/blob/main/LICENSE)
