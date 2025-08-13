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
REQUIRED_ENV_VARS = ["GCP_PROJECT_ID", "GCP_SPANNER_INSTANCE_ID", "GCP_SPANNER_DATABASE_NAME"]


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
config = {"development": DevelopmentConfig, "production": ProductionConfig, "default": DevelopmentConfig}


def validate_config_or_exit(config: Config) -> None:
    """Ensure the configuration is valid"""
    # Ensure GCP Spanner is configured
    for var in REQUIRED_ENV_VARS:
        if not getattr(config, var):
            logger.error("Environment variable %s must be set", var)
            sys.exit(1)


def get_config() -> Config:
    """Get the appropriate configuration object based on environment."""
    env = os.getenv("APP_ENV", "default")
    app_config = config[env]()
    validate_config_or_exit(app_config)
    return app_config
