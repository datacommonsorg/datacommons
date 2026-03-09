# Copyright 2025 Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# models.py
import sqlalchemy as sa
from sqlalchemy.types import Boolean, String

from datacommons_db.models.base import Base

OBSERVATION_TABLE_NAME = "Observation"


class ObservationRecord(Base):
    """
    Represents a statistical observation of a variable.
    """

    __tablename__ = OBSERVATION_TABLE_NAME

    # Composite Primary Key
    variable_measured = sa.Column(String(1024), sa.ForeignKey("Node.subject_id"), primary_key=True)
    observation_about = sa.Column(String(1024), sa.ForeignKey("Node.subject_id"), primary_key=True)
    facet_id = sa.Column(String(1024), sa.ForeignKey("Node.subject_id"), primary_key=True) # TODO: Is facet_id a DCID?
    
    # Store the org.datacommons.Observations map<string, string> natively as JSON
    # This allows direct querying into the keys (dates) and values within Spanner
    observations = sa.Column(sa.LargeBinary, nullable=False)
    
    import_name = sa.Column(String(1024), nullable=False, index=True)
    provenance_url = sa.Column(String(1024), nullable=False)

    # Optional metadata
    observation_period = sa.Column(String(1024))
    measurement_method = sa.Column(String(1024))
    unit = sa.Column(String(1024))
    scaling_factor = sa.Column(String(1024))
    is_dc_aggregate = sa.Column(Boolean)

    # RELATIONSHIPS
    variable_node = relationship("NodeRecord", foreign_keys=[variable_measured], lazy="joined")
    entity_node = relationship("NodeRecord", foreign_keys=[observation_about], lazy="joined")
    facet_node = relationship("NodeRecord", foreign_keys=[facet_id], lazy="joined")

    def __repr__(self):
        return f"<ObservationRecord(variable_measured='{self.variable_measured}', observation_about='{self.observation_about}', facet_id='{self.facet_id}')>"

