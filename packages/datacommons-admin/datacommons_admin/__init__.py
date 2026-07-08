"""CLI package for administering Data Commons instances in GCP."""

import importlib.metadata

try:
    __version__ = importlib.metadata.version("datacommons-admin")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0-dev"
