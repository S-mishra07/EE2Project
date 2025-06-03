def normalize_data(df):
    """Normalize the DataFrame using Min-Max scaling."""
    return (df - df.min()) / (df.max() - df.min())

def handle_missing_values(df):
    """Fill missing values in the DataFrame."""
    return df.fillna(method='ffill').fillna(method='bfill')

def feature_engineering(df):
    """Create additional features for the model."""
    df['price_diff'] = df['avg_sell_price'] - df['avg_buy_price']
    df['demand_change'] = df['demand'].diff().fillna(0)
    return df

def preprocess_data(df):
    """Preprocess the energy data."""
    df = handle_missing_values(df)
    df = feature_engineering(df)
    df = normalize_data(df)
    return df