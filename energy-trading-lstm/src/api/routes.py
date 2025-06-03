from flask import Blueprint, jsonify, request
from src.models.lstm import LSTMModel
from src.models.trading_strategy import TradingStrategy

api_bp = Blueprint('api', __name__)

lstm_model = LSTMModel()
trading_strategy = TradingStrategy()

@api_bp.route('/predict', methods=['POST'])
def predict():
    data = request.json
    if not data:
        return jsonify({'error': 'No input data provided'}), 400
    
    prediction = lstm_model.predict(data)
    return jsonify({'prediction': prediction})

@api_bp.route('/trade', methods=['POST'])
def trade():
    data = request.json
    if not data:
        return jsonify({'error': 'No trading data provided'}), 400
    
    action = trading_strategy.make_decision(data)
    return jsonify({'action': action})