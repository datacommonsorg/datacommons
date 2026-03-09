import sys
import os

# Ensure the package is in the Python path
sys.path.append(
    os.path.join(os.path.dirname(__file__), "..", "packages", "datacommons-api")
)
sys.path.append(
    os.path.join(os.path.dirname(__file__), "..", "packages", "datacommons-db")
)

from sqlalchemy import select
from datacommons_api.core.config import app_config
from datacommons_db.session import get_session, initialize_db
from datacommons_db.models.node import NodeModel
from datacommons_db.models.edge import EdgeModel

CORE_NODES = [
    # RDF
    {"subject_id": "rdf:type", "types": ["rdf:Property"], "value": "type"},
    {"subject_id": "rdf:Property", "types": ["rdfs:Class"], "value": "Property"},
    # RDFS
    {"subject_id": "rdfs:Class", "types": ["rdfs:Class"], "value": "Class"},
    {"subject_id": "rdfs:label", "types": ["rdf:Property"], "value": "label"},
    {"subject_id": "rdfs:comment", "types": ["rdf:Property"], "value": "comment"},
    {"subject_id": "rdfs:domain", "types": ["rdf:Property"], "value": "domain"},
    {"subject_id": "rdfs:range", "types": ["rdf:Property"], "value": "range"},
    {"subject_id": "rdfs:subClassOf", "types": ["rdf:Property"], "value": "subClassOf"},
    {
        "subject_id": "rdfs:subPropertyOf",
        "types": ["rdf:Property"],
        "value": "subPropertyOf",
    },
    # XSD
    {"subject_id": "xsd:string", "types": ["rdfs:Class"], "value": "string"},
    {"subject_id": "xsd:boolean", "types": ["rdfs:Class"], "value": "boolean"},
    {"subject_id": "xsd:int", "types": ["rdfs:Class"], "value": "int"},
    {"subject_id": "xsd:float", "types": ["rdfs:Class"], "value": "float"},
    {"subject_id": "xsd:double", "types": ["rdfs:Class"], "value": "double"},
    {"subject_id": "xsd:decimal", "types": ["rdfs:Class"], "value": "decimal"},
    {"subject_id": "xsd:date", "types": ["rdfs:Class"], "value": "date"},
    {"subject_id": "xsd:dateTime", "types": ["rdfs:Class"], "value": "dateTime"},
    # Schema.org
    {"subject_id": "schema:name", "types": ["rdf:Property"], "value": "name"},
    {
        "subject_id": "schema:description",
        "types": ["rdf:Property"],
        "value": "description",
    },
    # DataCommons Custom
    {"subject_id": "dcid:dcid", "types": ["rdf:Property"], "value": "dcid"},
]


def bootstrap():
    print("Initializing database connection...")
    initialize_db(
        app_config.GCP_PROJECT_ID,
        app_config.GCP_SPANNER_INSTANCE_ID,
        app_config.GCP_SPANNER_DATABASE_NAME,
    )

    session = get_session(
        app_config.GCP_PROJECT_ID,
        app_config.GCP_SPANNER_INSTANCE_ID,
        app_config.GCP_SPANNER_DATABASE_NAME,
    )
    try:
        print(f"Bootstrapping {len(CORE_NODES)} core nodes...")

        for node_data in CORE_NODES:
            # Check if it exists
            existing = (
                session.execute(
                    select(NodeModel).filter_by(subject_id=node_data["subject_id"])
                )
                .unique()
                .scalar_one_or_none()
            )

            if not existing:
                print(f"Creating: {node_data['subject_id']}")
                node = NodeModel(**node_data)
                session.add(node)
            else:
                print(f"Skipping (exists): {node_data['subject_id']}")

        session.commit()
        print("Bootstrap complete!")

    except Exception as e:
        session.rollback()
        print(f"Error during bootstrap: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    bootstrap()
