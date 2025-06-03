from flask import Flask
from src.api.routes import api_routes

app = Flask(__name__)

# Register API routes
app.register_blueprint(api_routes)

if __name__ == '__main__':
    app.run(debug=True)