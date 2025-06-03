# filepath: energy-trading-lstm/src/utils/constants.py
# This file contains constant values used throughout the project.

# Trading thresholds
BUY_THRESHOLD = 0.05  # Threshold for buying energy
SELL_THRESHOLD = 0.05  # Threshold for selling energy
MIN_STORAGE = 10  # Minimum storage level before buying
MAX_STORAGE = 100  # Maximum storage level

# LSTM model parameters
LSTM_INPUT_SIZE = 10  # Number of input features for LSTM
LSTM_HIDDEN_SIZE = 50  # Number of hidden units in LSTM
LSTM_NUM_LAYERS = 2  # Number of LSTM layers
LSTM_OUTPUT_SIZE = 1  # Output size for predictions

# Training parameters
EPOCHS = 100  # Number of training epochs
BATCH_SIZE = 32  # Batch size for training
LEARNING_RATE = 0.001  # Learning rate for optimizer

# API settings
API_URL = "http://localhost:5000"  # Base URL for API
TIMEOUT = 5  # Timeout for API requests in seconds

# Miscellaneous
DATA_PATH = "data/historical_data.csv"  # Path to historical data file
LOGGING_LEVEL = "INFO"  # Logging level for the application