from sqlalchemy.dialects import registry

# Register the 'spanner' dialect to prevent validation warnings in unit tests.
# This ensures SQLAlchemy recognizes Spanner-specific mapped arguments (e.g.,
# `spanner_interleave_in`) even when no Spanner engine is active / automatically loaded.
registry.register(
    "spanner", "google.cloud.sqlalchemy_spanner.sqlalchemy_spanner", "SpannerDialect"
)
