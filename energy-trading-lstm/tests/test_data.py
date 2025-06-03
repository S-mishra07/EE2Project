import unittest
from src.data.data_loader import load_historical_data
from src.data.preprocessor import prepare_training_data

class TestDataLoading(unittest.TestCase):

    def test_load_historical_data(self):
        # Test loading historical data
        data = load_historical_data(days=100)
        self.assertIsNotNone(data)
        self.assertGreater(len(data), 0)

    def test_prepare_training_data(self):
        # Test preprocessing of data
        sample_data = {
            'avg_buy_price': [10, 20, 30],
            'avg_sell_price': [15, 25, 35],
            'demand': [5, 10, 15]
        }
        df = prepare_training_data(sample_data)
        self.assertIn('time_of_day', df.columns)
        self.assertIn('sunlight', df.columns)

if __name__ == '__main__':
    unittest.main()