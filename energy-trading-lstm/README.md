# Energy Trading LSTM Project

This project implements a predictive algorithm using an LSTM model to optimize buying, selling, and storing energy in order to minimize losses. The application integrates historical energy data, processes it, and utilizes machine learning techniques to make informed trading decisions.

## Project Structure

```
energy-trading-lstm
├── src
│   ├── data
│   │   ├── data_loader.py       # Functions for loading historical energy data
│   │   └── preprocessor.py       # Functions for preprocessing the loaded data
│   ├── models
│   │   ├── lstm.py               # LSTM model architecture
│   │   └── trading_strategy.py    # Trading strategy implementation
│   ├── utils
│   │   ├── constants.py          # Constant values used throughout the project
│   │   └── helpers.py            # Utility functions for various tasks
│   ├── api
│   │   ├── routes.py             # API routes for fetching predictions and trading data
│   │   └── server.py             # Flask server setup and integration of API routes
│   └── main.py                   # Entry point for the application
├── tests
│   ├── test_data.py              # Unit tests for data loading and preprocessing
│   ├── test_models.py            # Unit tests for LSTM model and trading strategy
│   └── test_trading.py           # Tests for overall trading logic and decision-making
├── config
│   └── config.yaml               # Configuration settings for the application
├── requirements.txt              # Python dependencies required for the project
├── setup.py                      # Packaging information for the project
└── README.md                     # Documentation for the project
```

## Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   cd energy-trading-lstm
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Configure the application settings in `config/config.yaml` as needed.

## Usage

To run the application, execute the following command:
```
python src/main.py
```

The server will start, and you can access the API endpoints to fetch predictions and trading data.

## Contributing

Contributions are welcome! Please submit a pull request or open an issue for any enhancements or bug fixes.

## License

This project is licensed under the MIT License. See the LICENSE file for more details.