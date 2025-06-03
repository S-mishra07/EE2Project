def log_message(message):
    """Logs a message to the console."""
    print(f"[LOG] {message}")

def calculate_performance_metrics(predictions, actuals):
    """Calculates performance metrics such as MSE and MAE."""
    mse = ((predictions - actuals) ** 2).mean()
    mae = (abs(predictions - actuals)).mean()
    return mse, mae

def visualize_data(data, title="Data Visualization"):
    """Visualizes the given data using matplotlib."""
    import matplotlib.pyplot as plt
    
    plt.figure(figsize=(10, 5))
    plt.plot(data)
    plt.title(title)
    plt.xlabel("Time")
    plt.ylabel("Value")
    plt.grid()
    plt.show()