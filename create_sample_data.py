import os
import pandas as pd
import numpy as np

# Ensure directory structure exists
os.makedirs('data/raw', exist_ok=True)
os.makedirs('data/processed', exist_ok=True)
os.makedirs('models', exist_ok=True)

# Set seed for reproducibility
np.random.seed(42)

# Generate dates for 36 months
dates = pd.date_range(start='2023-01-01', periods=36, freq='ME')

companies = ['Company_A', 'Company_B', 'Company_C']
data = []

for company in companies:
    for i, date in enumerate(dates):
        if company == 'Company_A':
            # Declining trend (distress warning)
            cash_flow = 100000 - (i * 1800) + np.random.normal(0, 500)
            profit = 50000 - (i * 900) + np.random.normal(0, 300)
            expenses = 40000 + (i * 400) + np.random.normal(0, 300)
            loans = 5000 + (i * 1000) + np.random.normal(0, 200)
        elif company == 'Company_B':
            # Healthy growing trend
            cash_flow = 80000 + (i * 1500) + np.random.normal(0, 400)
            profit = 40000 + (i * 800) + np.random.normal(0, 300)
            expenses = 35000 + (i * 500) + np.random.normal(0, 300)
            loans = 12000 - (i * 200) + np.random.normal(0, 100)
        else: # Company_C
            # Highly unstable, rapid descent into bankruptcy risk
            cash_flow = 60000 - (i * 2200) + np.random.normal(0, 800)
            profit = 20000 - (i * 1100) + np.random.normal(0, 500)
            expenses = 30000 + (i * 800) + np.random.normal(0, 400)
            loans = 25000 + (i * 2000) + np.random.normal(0, 400)
        
        # Ensure cash flow doesn't go negative in raw historical data (except maybe near the very end)
        cash_flow = max(0.0, cash_flow)
        loans = max(0.0, loans)
        
        data.append({
            'date': date.strftime('%Y-%m-%d'),
            'company': company,
            'cash_flow': float(cash_flow),
            'profit': float(profit),
            'expenses': float(expenses),
            'loans': float(loans)
        })

df = pd.DataFrame(data)
df.to_csv('data/raw/financial_data.csv', index=False)
print("Sample data successfully generated and saved to data/raw/financial_data.csv!")
print(df.head())
