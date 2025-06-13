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
from sqlalchemy.types import String

from datacommons.db.models.base import Base


class ObservationModel(Base):
    """
    Represents a statistical observation of a variable.
    """

    __tablename__ = "Observation"

    variable_measured = sa.Column(String(1024), nullable=False, primary_key=True)
    observation_about = sa.Column(String(1024), nullable=False, primary_key=True)
    import_name = sa.Column(String(1024), nullable=False, primary_key=True)
    observation_period = sa.Column(String(1024), nullable=True)
    measurement_method = sa.Column(String(1024), nullable=True)
    unit = sa.Column(String(1024), nullable=True)
    scaling_factor = sa.Column(String(1024), nullable=True)
    observations = sa.Column(sa.LargeBinary, nullable=False)
    provenance_url = sa.Column(String(1024), nullable=False)

    def __repr__(self):
        return f"<ObservationModel(variable_measured='{self.variable_measured}', observation_about='{self.observation_about}', import_name='{self.import_name}')>"
