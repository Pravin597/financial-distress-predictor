import os
import pickle
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.callbacks import EarlyStopping

def create_sequences(data, seq_length=12):
    """
    Creates sliding-window sequences of seq_length.
    Input shape: (N, num_features)
    X output shape: (samples, seq_length, num_features)
    y output shape: (samples,) - target is the NEXT month's cash_flow (index 0)
    """
    X, y = [], []
    for i in range(len(data) - seq_length):
        X.append(data[i : i + seq_length])
        y.append(data[i + seq_length, 0])  # Index 0 is cash_flow
    return np.array(X), np.array(y)

def build_model(input_shape):
    """
    Builds the LSTM network.
    """
    model = Sequential([
        LSTM(units=256, return_sequences=True, input_shape=input_shape),
        Dropout(0.05),
        LSTM(units=128, return_sequences=False),
        Dropout(0.05),
        Dense(units=64, activation='relu'),
        Dense(units=32, activation='relu'),
        Dense(units=1)  # Predicts single value (cash flow)
    ])
    return model

def main():
    print("TensorFlow version:", tf.__version__)
    
    # 1. Load data
    data_path = 'data/raw/financial_data.csv'
    if not os.path.exists(data_path):
        raise FileNotFoundError(f"Missing data file: {data_path}. Please run create_sample_data.py first.")
    
    df = pd.read_csv(data_path)
    
    # 2. Preprocessing & scaling
    features = ['cash_flow', 'profit', 'expenses', 'loans']
    
    # Handle missing values if any
    df[features] = df[features].ffill().bfill()
    
    # Normalize features between 0 and 1
    scaler = MinMaxScaler(feature_range=(0, 1))
    df[features] = scaler.fit_transform(df[features])
    
    # Save the scaler for inference
    os.makedirs('models', exist_ok=True)
    with open('models/scaler.pkl', 'wb') as f:
        pickle.dump(scaler, f)
    print("Scaler saved to models/scaler.pkl")
    
    # 3. Create sequences group-by-company
    X_all, y_all = [], []
    for company, group in df.groupby('company'):
        # Extract features for this company in chronological order
        company_data = group[features].values
        if len(company_data) > 12:
            X_comp, y_comp = create_sequences(company_data, seq_length=12)
            X_all.append(X_comp)
            y_all.append(y_comp)
        else:
            print(f"Skipping {company} due to insufficient data length ({len(company_data)})")
            
    X = np.concatenate(X_all, axis=0)
    y = np.concatenate(y_all, axis=0)
    
    print(f"Total dataset size: X shape = {X.shape}, y shape = {y.shape}")
    
    # 4. Split data (70% train, 30% validation)
    # Shuffle sequences randomly to break company ordering block bias during split
    indices = np.arange(len(X))
    np.random.shuffle(indices)
    X = X[indices]
    y = y[indices]
    
    split = int(len(X) * 0.7)
    X_train, y_train = X[:split], y[:split]
    X_val, y_val = X[split:], y[split:]
    
    print(f"Train size: X={X_train.shape}, y={y_train.shape}")
    print(f"Val size: X={X_val.shape}, y={y_val.shape}")
    
    # 5. Build and compile model
    model = build_model(input_shape=(12, len(features)))
    model.compile(
        optimizer=Adam(learning_rate=0.0002),
        loss='mean_squared_error',
        metrics=['mae']
    )
    model.summary()
    
    # 6. Train model
    early_stop = EarlyStopping(
        monitor='val_loss',
        patience=25,
        restore_best_weights=True
    )
    
    history = model.fit(
        X_train, y_train,
        epochs=500,
        batch_size=8,
        validation_data=(X_val, y_val),
        callbacks=[early_stop],
        verbose=1
    )
    
    # 7. Save model
    model_path = 'models/lstm_model.h5'
    model.save(model_path)
    print(f"Model saved successfully to {model_path}!")

if __name__ == '__main__':
    main()
