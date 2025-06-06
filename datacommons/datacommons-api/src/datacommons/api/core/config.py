import os
import sys
from datacommons.api.core.logging import get_logger

logger = get_logger(__name__)

class Config:
  """Base configuration."""
  # Database settings
  GCP_PROJECT_ID: str = os.getenv('GCP_PROJECT_ID', '')
  GCP_SPANNER_INSTANCE_ID: str = os.getenv('GCP_SPANNER_INSTANCE_ID', '')
  GCP_SPANNER_DATABASE_NAME: str = os.getenv('GCP_SPANNER_DATABASE_NAME', '')

class DevelopmentConfig(Config):
  """Development configuration."""
  DEBUG = True

class ProductionConfig(Config):
  """Production configuration."""
  DEBUG = False

# Configuration dictionary
config = {
  'development': DevelopmentConfig,
  'production': ProductionConfig,
  'default': DevelopmentConfig
}

def validate_config_or_exit(config: Config) -> None:
  """Ensure the configuration is valid"""
  # Ensure GCP Spanner is configured
  if not config.GCP_PROJECT_ID or not config.GCP_SPANNER_INSTANCE_ID or not config.GCP_SPANNER_DATABASE_NAME:
    logger.error("Environment variables GCP_PROJECT_ID, GCP_SPANNER_INSTANCE_ID, and GCP_SPANNER_DATABASE_NAME must be set")
    sys.exit(1)

def get_config() -> Config:
  """Get the appropriate configuration object based on environment."""
  env = os.getenv('APP_ENV', 'default')
  app_config = config[env]()
  validate_config_or_exit(app_config)
  return app_config