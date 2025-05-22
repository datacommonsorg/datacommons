# Data Commons

Data Commons is an open source semantic graph database for modeling, querying, and analyzing interconnected data. It implements [RDF](https://www.w3.org/RDF/), [RDFS](https://www.w3.org/TR/rdf-schema/), [OWL](https://www.w3.org/OWL/), and [SHACL](https://www.w3.org/TR/shacl/) standards, with schemas defined in [JSON-LD](https://json-ld.org/) for domain-specific data modeling.

Data Commons powers [datacommons.org](https://datacommons.org), Google's open knowledge graph that connects public data across domains like demographics, economics, health, and education.

## Getting Started

This guide covers setting up a local Data Commons, defining schemas in JSON-LD, adding data via the command-line interface, and querying relationships.

## Prerequisites

Before you begin, ensure you have the following installed:

- [Python](https://www.python.org/downloads/) 3.11 or higher
- [Hatch](https://hatch.pypa.io/latest/) (Python project manager)

### Installing Hatch

You can install Hatch using pip:

```bash
pip install hatch
```

## Setting Up Data Commons

This section will guide you through setting up Data Commons locally and defining your first custom schema and data.

### 1. Install Data Commons Locally

To get started, you'll need to check out the Data Commons repository and set up your local environment.

#### Check out the repository:

To get started, you'll need to check out the Data Commons repository and set up your local environment.

```bash
git clone https://github.org/datacommonsorg/datacommons
cd datacommons
```

#### Create a Hatch environment:


```bash
hatch env create
```

#### Start Data Commons:

```bash
datacommons api start
```

This will start the Data Commons API server on port 5000, ready to receive your schema and data.

### 2. Define Your Schema

Data Commons uses JSON-LD to define schemas, building upon RDF, RDFS, and SHACL for robust data modeling and validation. Let's create two simple JSON-LD documents: one for defining a "Person" schema and another for sample person data and their relationships.

`person-schema.jsonld`

This document defines a Person class with properties for name and friendOf under the local namespace. The friendOf property is constrained to be another Person and can have multiple values.

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
      "@id": "local:Person",
      "@type": "rdfs:Class",
      "rdfs:label":   "Person",
      "rdfs:comment": "A human being."
    },
    {
      "@id": "local:fullName",
      "@type": "rdf:Property",
      "rdfs:label":       "full name",
      "rdfs:comment":     "The person's full name.",
      "rdfs:domain":      { "@id": "local:Person" },
      "rdfs:range":       { "@id": "xsd:string" }
    },
    {
      "@id": "local:email",
      "@type": "rdf:Property",
      "rdfs:label":       "email address",
      "rdfs:comment":     "A contact email for the person.",
      "rdfs:domain":      { "@id": "local:Person" },
      "rdfs:range":       { "@id": "xsd:string" }
    },
    {
      "@id": "local:friend",
      "@type": "rdf:Property",
      "rdfs:label":       "friend",
      "rdfs:comment":     "Links one person to another person they know.",
      "rdfs:domain":      { "@id": "local:Person" },
      "rdfs:range":       { "@id": "local:Person" }
    }
  ]
}
```


`people.jsonld`

This document contains actual Person instances and defines a chain of "friendOf" relationships.

```json
[
  {
    "@context": {
      "ex": "http://example.org/schema/"
    },
    "@id": "local:Li",
    "@type": "local:Person",
    "local:name": "Li",
    "local:friendOf": "local:Sally"
  },
  {
    "@context": {
      "ex": "http://example.org/schema/"
    },
    "@id": "local:Sally",
    "@type": "local:Person",
    "local:name": "Sally",
    "local:friendOf": ["local:Li", "local:Maria", "local:John"]
  },
  {
    "@context": {
      "ex": "http://example.org/schema/"
    },
    "@id": "local:Maria",
    "@type": "local:Person",
    "local:name": "Maria",
    "local:friendOf": ["local:Sally", "local:Natalie"]
  },
  {
    "@context": {
      "ex": "http://example.org/schema/"
    },
    "@id": "local:John",
    "@type": "local:Person",
    "local:name": "John",
    "local:friendOf": ["local:Sally"]
  },
  {
    "@context": {
      "ex": "http://example.org/schema/"
    },
    "@id": "local:Natalie",
    "@type": "local:Person",
    "local:name": "Natalie",
    "local:friendOf": ["local:Maria"]
  }
]
```

### 3. Upload Your Schema and Data to Data Commons
In a separate terminal from where you started the Data Commons API, upload the schema and data documents using the datacommons client post nodes command.

#### Upload the schema:

```bash
datacommons client post nodes person-schema.jsonld
```

#### Upload the people data:

```bash
datacommons client post nodes people.jsonld
```

#### Verify imported data

View schema elements (classes and properties):
```bash
datacommons client get nodes --type rdfs:Class --type rdf:Property
```

View instances of a class:
```bash
datacommons client get nodes --type local:Person
```

View a specific node:
```bash
datacommons client get nodes --id local:Li
```

Output is in JSON-LD format.

#### Query relationships

Find mutual friends between two people:
```bash
datacommons client get nodes --query --from local:Li --from local:Sally --path "friendOf" --common
```

Check if two people are connected:
```bash
datacommons client get nodes --query --from local:Sally --path "friendOf" --to local:Maria
```

Find friends of friends:
```bash
datacommons client get nodes --query --from local:Natalie --path "friendOf/friendOf"
```

The syntax uses:
- `--from` to specify starting node(s)
- `--to` to specify target node(s)
- `--path` to define relationship(s) to traverse
- `--common` to find shared values
- Multiple relationships can be chained with `/` in the path

#### Search nodes by name

Exact match:
```bash
datacommons client get nodes --property local:fullName --value "Li"
```

Fuzzy match (LIKE):
```bash
datacommons client get nodes --property local:fullName --like "Li%"
```

Semantic search (vector similarity):
```bash
datacommons client get nodes --property local:fullName --similar "person named Lee"
```

Full text search:
```bash
datacommons client get nodes --search "Li"
```

