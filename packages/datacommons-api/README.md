# Data Commons API

> **Note**: This is an experimental project. For running your own Data Commons instance, see [datacommonsorg/website](https://github.com/datacommonsorg/website). For accessing the public Data Commons knowledge graph, please visit [datacommons.org](https://github.com/datacommonsorg/website).

Data Commons is an open source semantic graph database for modeling, querying, and analyzing interconnected data. It implements [RDF](https://www.w3.org/RDF/), [RDFS](https://www.w3.org/TR/rdf-schema/), [OWL](https://www.w3.org/OWL/), and [SHACL](https://www.w3.org/TR/shacl/) standards, with schemas defined in [JSON-LD](https://json-ld.org/) for domain-specific data modeling.

## Setting Up Data Commons Locally

This section will guide you through setting up Data Commons locally and defining your first custom schema and data.

### 1. Install Data Commons

To get started, you'll need to check out the Data Commons repository and set up your local environment.

#### Clone the repository:

```bash
git clone https://github.org/datacommonsorg/datacommons
cd datacommons
```

The repository contains two main components:
- `datacommons-admin`: Command-line tools for administering Data Commons
- `datacommons-cli`: Command-line interface for interacting with Data Commons

And three experimental packages:
- `datacommons-api`: [experimental] The REST API server for interacting with Data Commons
- `datacommons-db`: [experimental] The database layer for storing and querying data
- `datacommons-schema`: [experimental] Schema management and validation tools

#### Create a virtual environment with uv

```bash
uv sync
```

#### Run Tests

Run the test suite to verify your setup:

```bash
uv run pytest
```

Tests are also run automatically before pushing changes.

#### Configure GCP Spanner Environment Variables

Before starting the server, you need to set up your GCP Spanner environment variables. These are required for the application to connect to your Spanner database. The application will initialize a new database from scratch using these settings:

```bash
export GCP_PROJECT_ID="your-gcp-project-id"
export GCP_SPANNER_INSTANCE_ID="your-spanner-instance-id"
export GCP_SPANNER_DATABASE_NAME="your-spanner-database-name"
```

Replace the values with your actual GCP project and Spanner instance details or put them in a `.env` file in the root of the repository. You can find these in your Google Cloud Console under the Spanner section. Make sure you have the necessary permissions to create and modify databases in your Spanner instance.

#### Start Data Commons:

Launch Data Commons API server on port 5000, ready to receive your schema and data. CLI arguments override .env settings.

```bash
# Standard start
uv run datacommons-api start

# Development mode (with auto-reload)
uv run datacommons-api start --reload

# Override Spanner credentials config via CLI
uv run datacommons-api start \
  --gcp-project-id="your-gcp-project-id" \
  --gcp-spanner-instance-id="your-spanner-instance-id" \
  --gcp-spanner-database-name="your-spanner-database-name"
```


### 2. Define Your Schema

Data Commons uses JSON-LD to define schemas, building upon RDF, RDFS, and SHACL for robust data modeling and validation. The repository includes example schema and data files in the `examples` directory:

- `examples/person-schema.jsonld`: Defines a Person class with properties for name, email, and friend relationships
- `examples/people.jsonld`: Contains sample Person instances and their relationships

Here's an example of the Person schema:

```json
{
  "@context": {
    "rdf":   "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs":  "http://www.w3.org/2000/01/rdf-schema#",
    "xsd":   "http://www.w3.org/2001/XMLSchema#",
    "local": "http://localhost:5000/schema/local/"
  },
  "@graph": [
    {
      "@id": "local:Li",
      "@type": "local:Person",
      "local:name": "Li",
      "local:friendOf": [
        {
          "@id": "local:Sally"
        }
      ]
    },
    {
      "@id": "local:Sally",
      "@type": "local:Person",
      "local:name": "Sally",
      "local:friendOf": [
        {
          "@id": "local:Li"
        },
        {
          "@id": "local:Maria"
        },
        {
          "@id": "local:John"
        }
      ]
    },
    {
      "@id": "local:Maria",
      "@type": "local:Person",
      "local:name": "Maria",
      "local:friendOf": [
        {
          "@id": "local:Sally"
        },
        {
          "@id": "local:Natalie"
        }
      ]
    },
    {
      "@id": "local:John",
      "@type": "local:Person",
      "local:name": "John",
      "local:friendOf": [
        {
          "@id": "local:Sally"
        }
      ]
    },
    {
      "@id": "local:Natalie",
      "@type": "local:Person",
      "local:name": "Natalie",
      "local:friendOf": [
        {
          "@id": "local:Maria"
        }
      ]
    }
  ]
}
```

### 3. Upload Your Schema and Data to Data Commons

In a separate terminal from where you started the Data Commons API, upload the schema and data documents using the datacommons client post nodes command.

#### Upload the schema:

From the repository's root directory, run:

```bash
curl -X POST "http://localhost:5000/nodes/" -H "Content-Type: application/json" -d @examples/person-schema.jsonld

# With default provenance
curl -X POST "http://localhost:5000/nodes" \
  -H "Content-Type: application/json" \
  -d @examples/person-schema.jsonld
```

#### Upload the people data:

```bash
curl -X POST "http://localhost:5000/nodes" -H "Content-Type: application/json" -d @examples/people.jsonld

# With default provenance
curl -X POST "http://localhost:5000/nodes" \
  -H "Content-Type: application/json" \
  -d @examples/people.jsonld
```

#### Verify imported data

View schema elements (classes and properties):
```bash
curl -X GET "http://localhost:5000/nodes/?type=rdfs:Class&type=rdf:Property"
```

You should see the response:

```json
{
  "@context": {
    "@vocab": "http://localhost:5000/schema/local/",
    "local": "http://localhost:5000/schema/local/",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "xsd": "http://www.w3.org/2001/XMLSchema#"
  },
  "@graph": [
    {
      "@id": "local:Person",
      "@type": [
        "rdfs:Class"
      ],
      "rdfs:comment": {
        "@value": "A human being."
      },
      "rdfs:label": {
        "@value": "Person"
      }
    },
    {
      "@id": "local:friendOf",
      "@type": [
        "rdf:Property"
      ],
      "rdfs:comment": {
        "@value": "Links one person to another person they know."
      },
      "rdfs:domain": {
        "@id": "local:Person"
      },
      "rdfs:label": {
        "@value": "friend of"
      },
      "rdfs:range": {
        "@id": "local:Person"
      }
    },
    {
      "@id": "local:name",
      "@type": [
        "rdf:Property"
      ],
      "rdfs:comment": {
        "@value": "The person's name."
      },
      "rdfs:domain": {
        "@id": "local:Person"
      },
      "rdfs:label": {
        "@value": "name"
      },
      "rdfs:range": {
        "@id": "xsd:string"
      }
    }
  ]
}
```

View Person instances:
```bash
curl -X GET "http://localhost:5000/nodes/?type=local:Person"
```

You should see the:

```json
{
  "@context": {
    "@vocab": "http://localhost:5000/schema/local/",
    "local": "http://localhost:5000/schema/local/",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "xsd": "http://www.w3.org/2001/XMLSchema#"
  },
  "@graph": [
    {
      "@id": "local:Person",
      "@type": [
        "rdfs:Class"
      ],
      "rdfs:comment": {
        "@value": "A human being."
      },
      "rdfs:label": {
        "@value": "Person"
      }
    },
    {
      "@id": "local:friendOf",
      "@type": [
        "rdf:Property"
      ],
      "rdfs:comment": {
        "@value": "Links one person to another person they know."
      },
      "rdfs:domain": {
        "@id": "local:Person"
      },
      "rdfs:label": {
        "@value": "friend of"
      },
      "rdfs:range": {
        "@id": "local:Person"
      }
    },
    {
      "@id": "local:name",
      "@type": [
        "rdf:Property"
      ],
      "rdfs:comment": {
        "@value": "The person's name."
      },
      "rdfs:domain": {
        "@id": "local:Person"
      },
      "rdfs:label": {
        "@value": "name"
      },
      "rdfs:range": {
        "@id": "xsd:string"
      }
    }
  ]
}
```


## API Key Configuration & Diagnostics

The Data Commons API server requires a valid `DC_API_KEY` to authenticate federated queries to the central Data Commons API backend (`api.datacommons.org`). This section describes how to configure the key, how the server handles errors, and how to monitor the server's health status.

### 1. Configuration Environment Variables

You can configure the server's API key behavior using the following environment variables:

| Environment Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `DC_API_KEY` | String | None | The Google API key used to authenticate requests to the central Data Commons API (`api.datacommons.org`). |
| `DC_API_KEY_OPTIONAL` | Boolean | `false` | If set to `true`, the server is allowed to boot even if `DC_API_KEY` is missing or empty. If a key *is* provided, it will still be validated on startup. Useful for local offline development. |
| `DC_API_KEY_STRICT_VALIDATION` | Boolean | `false` | If set to `true`, the server will fail-fast and halt startup if the central API is unreachable (network timeout or 5xx error). By default (Resilient Fail-Open), the server will log a warning, boot in degraded mode, and attempt background re-validation. |

### 2. Runtime Error Handling & Propagation

If a federated request to `api.datacommons.org` fails with a credential error at runtime, the server intercepts it and returns a standardized, secure JSON response with an appropriate HTTP status code. The server's sensitive API key is completely redacted from all tracebacks and logs.

#### Standardized Error Payload (HTTP 401 / 403)
```json
{
  "error": "Unauthorized",
  "message": "The Data Commons API server key is invalid or expired. Please contact the administrator.",
  "code": "API_KEY_UNAUTHORIZED"
}
```

*   **HTTP 401 (API_KEY_UNAUTHORIZED):** Returned when the configured `DC_API_KEY` is invalid, expired, or deactivated.
*   **HTTP 403 (API_KEY_FORBIDDEN):** Returned when the configured `DC_API_KEY` lacks permissions to access the requested resource.

### 3. Health & Status Diagnostics (`/healthz`)

The server exposes a detailed health check endpoint at `/healthz` (with a hidden alias at `/status`). This endpoint returns the server's overall status, degraded state, and detailed API key health:

#### Healthy State (HTTP 200 OK)
Returned when the API key has been successfully verified (or when the key check was bypassed because `DC_API_KEY_OPTIONAL=true` and no key was provided):
```json
{
  "status": "healthy",
  "degraded": false,
  "api_key_status": "verified"
}
```

#### Degraded Warning State (HTTP 200 OK)
Returned when the server booted successfully but the central API was unreachable due to transient network issues:
```json
{
  "status": "degraded",
  "degraded": true,
  "api_key_status": "unverified",
  "critical": false,
  "message": "Data Commons API key is unverified due to network issues. Operating in degraded fail-open mode."
}
```
*Note: A background worker runs in a non-blocking thread, retrying validation every 1 minute. If validation succeeds later, the server automatically exits degraded mode.*

#### Unhealthy / Outage State (HTTP 503 Service Unavailable)
Returned if the API key is confirmed to be invalid (401/403) or if the background re-validation worker has failed continuously for **30 minutes** (indicating a persistent network outage or misconfiguration):
```json
{
  "status": "unhealthy",
  "degraded": true,
  "api_key_status": "invalid",
  "critical": true,
  "message": "Data Commons API key validation has failed continuously. Spanner queries remain available."
}
```
*Use this endpoint in Kubernetes liveness/readiness probes or load-balancer health checks to trigger automated alerts and rollbacks.*
