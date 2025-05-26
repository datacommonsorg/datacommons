import os

PROJECT_ID = "datcom-website-dev"
INSTANCE_ID = "dan-dc2-dc-spanner"
DATABASE_NAME = "dc-spanner-db"

#PROJECT_ID = "datcom-store"
#INSTANCE_ID = "dc-kg-test"
#DATABASE_NAME = "dc_graph_6"

class Config:
    """Base configuration."""
    # Database settings
    SPANNER_PROJECT_ID: str = os.getenv('SPANNER_PROJECT_ID', 'datcom-website-dev')
    SPANNER_INSTANCE_ID: str = os.getenv('SPANNER_INSTANCE_ID', 'dan-dc2-dc-spanner')
    SPANNER_DATABASE_NAME: str = os.getenv('SPANNER_DATABASE_NAME', 'dc-spanner-db')

    #SPANNER_PROJECT_ID: str = os.getenv('SPANNER_PROJECT_ID', 'datcom-store')
    #SPANNER_INSTANCE_ID: str = os.getenv('SPANNER_INSTANCE_ID', 'dc-kg-test')
    #SPANNER_DATABASE_NAME: str = os.getenv('SPANNER_DATABASE_NAME', 'dc_graph_5')

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
    env = os.getenv('APP_ENV', 'default')  # Using APP_ENV instead of FLASK_ENV
    return config[env]()  # Instantiate the config class