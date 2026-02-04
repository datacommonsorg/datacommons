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

import os
import sys

from datacommons_api.core.logging import get_logger

logger = get_logger(__name__)

# Required environment variables
REQUIRED_ENV_VARS = [
    "GCP_PROJECT_ID",
    "GCP_SPANNER_INSTANCE_ID",
    "GCP_SPANNER_DATABASE_NAME",
]


class Config:
    """Base configuration."""

    # Database settings
    GCP_PROJECT_ID: str = os.getenv("GCP_PROJECT_ID", "")
    GCP_SPANNER_INSTANCE_ID: str = os.getenv("GCP_SPANNER_INSTANCE_ID", "")
    GCP_SPANNER_DATABASE_NAME: str = os.getenv("GCP_SPANNER_DATABASE_NAME", "")


class DevelopmentConfig(Config):
    """Development configuration."""

    DEBUG = True


class ProductionConfig(Config):
    """Production configuration."""

    DEBUG = False


# Configuration dictionary
config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}


# Default configuration
app_config = config[os.getenv("APP_ENV", "default")]()

def validate_config_or_exit(config: Config) -> None:
    """Ensure the configuration is valid"""
    # Ensure GCP Spanner is configured
    for var in REQUIRED_ENV_VARS:
        if not getattr(config, var):
            logger.error("Environment variable %s must be set", var)
            sys.exit(1)


def initialize_config(
    gcp_project_id: str = "",
    gcp_spanner_instance_id: str = "",
    gcp_spanner_database_name: str = "",
) -> Config:
    """
    Initialize the configuration object based on environment or command line arguments.

    Args:
        gcp_project_id: Optional GCP project id.
        gcp_spanner_instance_id: Optional GCP Spanner instance id.
        gcp_spanner_database_name: Optional GCP Spanner database name.

    Returns:
        Config: The configuration object.
    """
    app_config.GCP_PROJECT_ID = gcp_project_id or app_config.GCP_PROJECT_ID
    app_config.GCP_SPANNER_INSTANCE_ID = gcp_spanner_instance_id or app_config.GCP_SPANNER_INSTANCE_ID
    app_config.GCP_SPANNER_DATABASE_NAME = gcp_spanner_database_name or app_config.GCP_SPANNER_DATABASE_NAME
    validate_config_or_exit(app_config)
    return app_config


def get_config() -> Config:
    """
    Get the configuration object.

    Returns:
        Config: The configuration object.
    """
    return app_config