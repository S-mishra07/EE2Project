def load_historical_data(api_url, local_file_path=None):
    import pandas as pd
    import requests
    import os

    # Load data from API
    if api_url:
        response = requests.get(api_url)
        if response.status_code == 200:
            data = response.json()
            df = pd.DataFrame(data)
        else:
            raise Exception(f"Failed to fetch data from API: {response.status_code}")
    else:
        df = pd.DataFrame()

    # Load data from local file if provided
    if local_file_path and os.path.exists(local_file_path):
        local_data = pd.read_csv(local_file_path)
        df = pd.concat([df, local_data], ignore_index=True)

    return df

def preprocess_data(df):
    # Handle missing values
    df.fillna(method='ffill', inplace=True)

    # Normalize data
    from sklearn.preprocessing import MinMaxScaler
    scaler = MinMaxScaler()
    scaled_data = scaler.fit_transform(df)
    
    return pd.DataFrame(scaled_data, columns=df.columns)

def get_feature_labels(df, feature_columns, label_column):
    X = df[feature_columns].values
    y = df[label_column].values
    return X, y