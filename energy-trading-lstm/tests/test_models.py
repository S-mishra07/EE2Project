import unittest
import torch
from src.models.lstm import LSTMModel
from src.models.trading_strategy import TradingStrategy

class TestLSTMModel(unittest.TestCase):
    def setUp(self):
        input_size = 10
        hidden_size = 20
        num_layers = 2
        self.model = LSTMModel(input_size, hidden_size, num_layers)

    def test_forward_pass(self):
        test_input = torch.randn(5, 1, 10)  # (sequence_length, batch_size, input_size)
        output = self.model(test_input)
        self.assertEqual(output.shape, (5, 1, 20))  # Check output shape

class TestTradingStrategy(unittest.TestCase):
    def setUp(self):
        self.strategy = TradingStrategy()

    def test_decision_making(self):
        current_price = 100
        predicted_price = 110
        decision = self.strategy.make_decision(current_price, predicted_price)
        self.assertIn(decision, ['buy', 'sell', 'hold'])  # Check if decision is valid

if __name__ == '__main__':
    unittest.main()