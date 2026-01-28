# Data Commons

[![CI](https://github.com/datacommonsorg/datacommons/actions/workflows/ci.yaml/badge.svg)](https://github.com/datacommonsorg/datacommons/actions/workflows/ci.yaml)

> **Note**: This is an experimental project. For running your own custom Data Commons instance, see [datacommonsorg/website](https://github.com/datacommonsorg/website). For accessing the public Data Commons knowledge graph, please visit [datacommons.org](https://github.com/datacommonsorg/website).

Data Commons is an open source semantic graph database for modeling, querying, and analyzing interconnected data. It implements [RDF](https://www.w3.org/RDF/), [RDFS](https://www.w3.org/TR/rdf-schema/), [OWL](https://www.w3.org/OWL/), and [SHACL](https://www.w3.org/TR/shacl/) standards, with schemas defined in [JSON-LD](https://json-ld.org/) for domain-specific data modeling.

Data Commons powers [datacommons.org](https://datacommons.org), Google's open knowledge graph that connects public data across domains like demographics, economics, health, and education.

## Getting Started

This guide covers setting up a local Data Commons, defining schemas in JSON-LD, adding data via the command-line interface, and querying relationships.

## Prerequisites

Before you begin, ensure you have the following installed:

- [Python](https://www.python.org/downloads/) 3.11 or higher
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python project manager)
- A Google Cloud Platform (GCP) project with Cloud Spanner enabled
- A Cloud Spanner instance and database (using Google Standard SQL) for storing the knowledge graph

## Setting Up Data Commons

This section will guide you through setting up Data Commons locally and defining your first custom schema and data.

### 1. Install Data Commons Locally

To get started, you'll need to check out the Data Commons repository and set up your local environment.

#### Clone the repository:

```bash
git clone https://github.org/datacommonsorg/datacommons
cd datacommons
```

The repository contains three main components:
- `datacommons-api`: The REST API server for interacting with Data Commons
- `datacommons-db`: The database layer for storing and querying data
- `datacommons-cli`: Command-line interface for interacting with Data Commons
- `datacommons-schema`: Schema management and validation tools

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

Replace the values with your actual GCP project and Spanner instance details. You can find these in your Google Cloud Console under the Spanner section. Make sure you have the necessary permissions to create and modify databases in your Spanner instance.

#### Start Data Commons:

Run the `datacommons` command using `uv` to start a local development server.

```bash
uv run datacommons api start
```

This will start the Data Commons API server on port 5000, ready to receive your schema and data.

Alternatively, you can set the spanner configuration using command line arguments, which will take precedence over environment variables:

```bash
uv run datacommons api start \
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
```

#### Upload the people data:

```bash
curl -X POST "http://localhost:5000/nodes/" -H "Content-Type: application/json" -d @examples/people.jsonld
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

### Schema Tools

Use the `datacommons schema` command to convert between MCF and JSON-LD formats.

```bash
# Convert with default settings
uv run datacommons schema mcf2jsonld data.mcf

# Convert with custom namespace and output file
uv run datacommons schema mcf2jsonld data.mcf -n "dc:https://datacommons.org/" -o output.jsonld

# Generate compact output
uv run datacommons schema mcf2jsonld data.mcf -c
```
