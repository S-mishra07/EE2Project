from flask import Flask
from api.routes import api_bp
import yaml

def load_config(config_path):
    with open(config_path, 'r') as file:
        config = yaml.safe_load(file)
    return config

def create_app():
    app = Flask(__name__)
    config = load_config('config/config.yaml')
    app.config.update(config)

    app.register_blueprint(api_bp)

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)