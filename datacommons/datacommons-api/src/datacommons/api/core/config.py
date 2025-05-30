import os

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

def get_config() -> Config:
  """Get the appropriate configuration object based on environment."""
  env = os.getenv('APP_ENV', 'default')
  return config[env]()  # Instantiate the config class