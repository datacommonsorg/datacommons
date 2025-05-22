from flask import Flask
from flask_restx import Api

# Create Flask app
app = Flask(__name__)

# Configure Flask-RESTX
api = Api(
    app,
    version='1.0',
    title='Data Commons API',
    description='A RESTful API for Data Commons',
    doc='/docs'
)

# Import and register namespaces
from .node import nodes_ns
api.add_namespace(nodes_ns)

