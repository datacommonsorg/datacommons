# Data Commons Schema Tools

This module provides command-line utilities and libraries for working with Data Commons schema formats, particularly focusing on conversion between MCF (Machine-Readable Common Format) and JSON-LD formats.

## Features

- MCF to JSON-LD conversion
- Schema validation and parsing
- Namespace management
- Compact and expanded JSON-LD output options

## Command Line Utilities

### MCF to JSON-LD Converter

The `mcf2jsonld` command converts MCF files to JSON-LD format, with support for custom namespaces and output formatting.

```bash
# Basic usage
datacommons mcf2jsonld input.mcf

# With custom namespace
datacommons mcf2jsonld input.mcf --namespace "schema:https://schema.org/"

# Output to file with compact format
datacommons mcf2jsonld input.mcf -o output.jsonld -c
```

#### Options

- `mcf_file`: Input MCF file path (required)
- `--namespace`, `-n`: Custom namespace to inject (format: "prefix:url")
- `--outfile`, `-o`: Output file path (defaults to stdout)
- `--compact`, `-c`: Generate compact JSON-LD output

## Module Components

### Converters

The module includes several converters for different schema formats:

- `mcf_to_jsonld`: Converts MCF nodes to JSON-LD format
- Additional converters for other schema formats

### Parsers

- `mcf_parser`: Parses MCF string content into structured nodes
- Support for various MCF syntax elements and properties

### Models

The module defines data models for:

- MCF nodes and properties
- JSON-LD document structure
- Schema validation rules

## Usage Examples

### Python API

```python
from datacommons.schema.parsers.mcf_parser import parse_mcf_string
from datacommons.schema.converters.mcf_to_jsonld import mcf_nodes_to_jsonld

# Parse MCF content
mcf_nodes = parse_mcf_string(mcf_content)

# Convert to JSON-LD
jsonld = mcf_nodes_to_jsonld(mcf_nodes, compact=True)
```

### Command Line

```bash
# Convert with default settings
datacommons mcf2jsonld data.mcf

# Convert with custom namespace and output file
datacommons mcf2jsonld data.mcf -n "dc:https://datacommons.org/" -o output.jsonld

# Generate compact output
datacommons mcf2jsonld data.mcf -c
```

## Dependencies

- Click (for CLI interface)
- Pydantic (for data validation)
- JSON-LD processing libraries

## Contributing

When contributing to this module:
1. Ensure all converters maintain data integrity
2. Add appropriate error handling
3. Include tests for new functionality
4. Update documentation for new features

## License

[Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0)
