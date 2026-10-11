import os
import pandas as pd
import numpy as np

def generate_csv(filename, company_name, trend_type):
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-31', periods=24, freq='ME')
    data = []
    
    for i, date in enumerate(dates):
        if trend_type == 'declining':
            # Cash flow declines from 105k to ~20k, profit drops, expenses rise
            cash = 105000 - (i * 3500) + np.random.normal(0, 3000)
            profit = 40000 - (i * 1800) + np.random.normal(0, 2000)
            expenses = 35000 + (i * 1000) + np.random.normal(0, 1500)
        elif trend_type == 'healthy':
            # Cash flow grows from 80k to ~120k, profit grows, expenses stable
            cash = 80000 + (i * 1800) + np.random.normal(0, 2500)
            profit = 30000 + (i * 800) + np.random.normal(0, 1500)
            expenses = 25000 + (i * 300) + np.random.normal(0, 1000)
        else: # critical
            # Cash flow plummets fast, goes negative near the end
            cash = 70000 - (i * 4200) + np.random.normal(0, 4000)
            profit = 15000 - (i * 2200) + np.random.normal(0, 2000)
            expenses = 30000 + (i * 1500) + np.random.normal(0, 1500)
            
        # Keep historical cash positive (distress shows in prediction)
        cash = max(5000.0, cash)
        
        data.append({
            'company': company_name,
            'date': date.strftime('%Y-%m-%d'),
            'cash_flow': int(cash),
            'profit': int(profit),
            'expenses': int(expenses)
        })
        
    df = pd.DataFrame(data)
    os.makedirs('test_cases', exist_ok=True)
    path = os.path.join('test_cases', filename)
    df.to_csv(path, index=False)
    print(f"Generated {trend_type} sample data: {path}")

if __name__ == '__main__':
    generate_csv('apex_logistics_warning.csv', 'Apex Logistics', 'declining')
    generate_csv('blue_sky_retail_healthy.csv', 'Blue Sky Retail', 'healthy')
    generate_csv('crater_mining_critical.csv', 'Crater Mining Co', 'critical')
    print("All test cases successfully generated in 'test_cases/' directory!")
