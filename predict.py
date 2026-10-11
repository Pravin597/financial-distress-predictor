import pickle
import numpy as np
import tensorflow as tf

def load_resources(model_path='models/lstm_model.h5', scaler_path='models/scaler.pkl'):
    """
    Loads the saved model and scaler.
    """
    model = tf.keras.models.load_model(model_path)
    with open(scaler_path, 'rb') as f:
        scaler = pickle.load(f)
    return model, scaler

def predict_future(model, scaler, last_12_months, num_months=12, pad_with_last=True):
    """
    Performs recursive multi-step forecasting to predict future cash flows.
    
    Parameters:
    - last_12_months: numpy array of shape (12, 4) representing the last 12 months of scaled features.
    - num_months: Number of months to forecast.
    - pad_with_last: If True, uses the last known profit, expenses, and loans for future timesteps.
                     If False, pads with 0.
    
    Returns:
    - denormalized_predictions: 1D array of length num_months containing predicted cash flow values in original scale.
    """
    predictions_scaled = []
    current_sequence = last_12_months.copy()
    
    for _ in range(num_months):
        # Reshape to (1, 12, 4) for model input
        X = current_sequence.reshape(1, 12, 4)
        # Predict next month's scaled cash flow
        next_month_scaled = model.predict(X, verbose=0)[0][0]
        predictions_scaled.append(next_month_scaled)
        
        # Construct the next feature row
        if pad_with_last:
            # Copy the last feature row, update cash_flow (index 0) with the new prediction
            next_row = current_sequence[-1].copy()
            next_row[0] = next_month_scaled
        else:
            # Pad with 0 for profit, expenses, loans
            next_row = np.array([next_month_scaled, 0.0, 0.0, 0.0])
            
        # Shift sequence window by 1 month
        current_sequence = np.vstack([current_sequence[1:], next_row])
        
    # Denormalize predictions
    predictions_scaled = np.array(predictions_scaled)
    # Create a dummy matrix of shape (num_months, 4) to fit the scaler expectation
    dummy_matrix = np.zeros((num_months, 4))
    dummy_matrix[:, 0] = predictions_scaled
    
    # Inverse transform and extract the first column (cash flow)
    denorm_matrix = scaler.inverse_transform(dummy_matrix)
    denormalized_predictions = denorm_matrix[:, 0]
    
    return denormalized_predictions

def detect_financial_distress(predictions, historical_last_cash=None):
    """
    Analyzes predicted cash flow values and triggers corresponding alerts.
    """
    alerts = []
    
    # Check if cash flow drops to or below 0
    if (predictions <= 0).any():
        alerts.append({
            'status': 'CRITICAL',
            'message': 'CRITICAL: Bankruptcy Risk! Predicted cash flow drops below zero.'
        })
    # Check for liquidity crisis (e.g. less than 15,000 cash flow)
    elif predictions.min() < 15000:
        alerts.append({
            'status': 'WARNING',
            'message': 'WARNING: Liquidity Crisis! Cash flow falls below safety threshold of $15,000.'
        })
    # Check for severe decline (e.g. drops by more than 40% compared to the start of prediction or last historical month)
    elif historical_last_cash is not None and predictions[-1] < historical_last_cash * 0.6:
        alerts.append({
            'status': 'WARNING',
            'message': f'WARNING: Severe Decline! Cash flow predicted to drop by over 40% (from ${historical_last_cash:,.0f} to ${predictions[-1]:,.0f}).'
        })
    elif len(predictions) > 0 and predictions[-1] < predictions[0] * 0.6:
        alerts.append({
            'status': 'WARNING',
            'message': f'WARNING: Severe Decline! Cash flow predicted to drop by over 40% over the next 12 months.'
        })
    
    if not alerts:
        alerts.append({
            'status': 'STABLE',
            'message': 'STABLE: Financial indicators appear healthy and stable.'
        })
        
    return alerts
