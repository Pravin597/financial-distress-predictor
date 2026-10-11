import os
import pickle
import pandas as pd
import numpy as np
import pdfplumber
import io
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from predict import load_resources, predict_future, detect_financial_distress
import database

app = Flask(__name__)
app.secret_key = 'antigravity_secret_session_key_1294871209348120'

# Initialize Database & Run Migrations
database.init_db()

# Paths to models
MODEL_PATH = 'models/lstm_model.h5'
SCALER_PATH = 'models/scaler.pkl'

# ================= LOGIN DECORATOR =================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Unauthorized. Please log in.'}), 401
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or not session.get('is_admin', False):
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Unauthorized. Admin access required.'}), 403
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

# ================= AUTHENTICATION ENDPOINTS =================

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if 'user_id' in session:
        return redirect(url_for('home'))
        
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return jsonify({'error': 'Username and password are required'}), 400
            
        user = database.verify_user(username, password)
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['is_admin'] = user.get('is_admin', False)
            return jsonify({'success': 'Logged in successfully', 'is_admin': session['is_admin']})
        else:
            return jsonify({'error': 'Invalid username or password'}), 401
            
    return render_template('login.html')

@app.route('/signup')
def signup_page():
    if 'user_id' in session:
        return redirect(url_for('home'))
    return render_template('signup.html')

@app.route('/register', methods=['POST'])
def register():
    if 'user_id' in session:
        return jsonify({'error': 'Already logged in'}), 400
        
    data = request.get_json() if request.is_json else request.form
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400
        
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters long'}), 400
        
    user = database.create_user(username, password)
    if user:
        session['user_id'] = user['id']
        session['username'] = user['username']
        return jsonify({'success': 'Registered and logged in successfully'})
    else:
        return jsonify({'error': 'Username is already taken'}), 409

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

# ================= WEB APP ROUTE =================

@app.route('/')
@login_required
def home():
    return render_template('index.html', username=session.get('username'), is_admin=session.get('is_admin', False))

# ================= ADMIN ROUTES =================

@app.route('/admin')
@admin_required
def admin_dashboard():
    return render_template('admin.html', username=session.get('username'))

@app.route('/api/admin/users', methods=['GET'])
@admin_required
def admin_get_users():
    users = database.get_all_users()
    return jsonify(users)

@app.route('/api/admin/companies', methods=['GET'])
@admin_required
def admin_get_companies():
    companies = database.get_all_companies()
    return jsonify(companies)

# ================= CRUD COMPANIES =================

@app.route('/api/companies', methods=['GET'])
@login_required
def get_companies():
    companies = database.get_companies_by_user(session['user_id'])
    return jsonify(companies)

@app.route('/api/companies', methods=['POST'])
@login_required
def add_company():
    data = request.get_json()
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Company name is required'}), 400
        
    company_id = database.create_company(name, session['user_id'])
    if company_id:
        # Return 201 Created (Fixed typo '21')
        return jsonify({'id': company_id, 'name': name}), 201
    return jsonify({'error': 'A company with this name already exists'}), 409

@app.route('/api/companies/<int:company_id>', methods=['DELETE'])
@login_required
def delete_company(company_id):
    success = database.delete_company(company_id, session['user_id'])
    if success:
        return jsonify({'success': 'Company deleted successfully'})
    return jsonify({'error': 'Company not found or unauthorized'}), 404

@app.route('/api/companies/<int:company_id>/rename', methods=['POST'])
@login_required
def rename_company(company_id):
    data = request.get_json()
    new_name = data.get('name', '').strip()
    if not new_name:
        return jsonify({'error': 'Company name is required'}), 400
        
    success = database.rename_company(company_id, session['user_id'], new_name)
    if success:
        return jsonify({'success': 'Company renamed successfully'})
    return jsonify({'error': 'Company not found, unauthorized, or name already exists'}), 400

@app.route('/api/companies/<int:company_id>/currency', methods=['POST'])
@login_required
def update_company_currency(company_id):
    if not database.verify_company_ownership(company_id, session['user_id']):
        return jsonify({'error': 'Company not found or unauthorized'}), 404
        
    data = request.get_json()
    currency = data.get('currency', '$').strip()
    if not currency:
        return jsonify({'error': 'Currency symbol is required'}), 400
        
    success = database.update_company_currency(company_id, session['user_id'], currency)
    if success:
        return jsonify({'success': 'Company currency updated successfully'})
    return jsonify({'error': 'Failed to update currency'}), 500


# ================= CA SHEET NOTES =================

@app.route('/api/companies/<int:company_id>/ca-sheet', methods=['GET'])
@login_required
def get_ca_sheet(company_id):
    notes = database.get_ca_sheet(company_id, session['user_id'])
    if notes is None:
        return jsonify({'error': 'Company not found or unauthorized'}), 404
    return jsonify({'ca_notes': notes})

@app.route('/api/companies/<int:company_id>/ca-sheet', methods=['POST'])
@login_required
def save_ca_sheet(company_id):
    data = request.get_json()
    notes = data.get('ca_notes', '').strip()
    success = database.save_ca_sheet(company_id, session['user_id'], notes)
    if success:
        return jsonify({'success': 'CA Audit Sheet saved successfully'})
    return jsonify({'error': 'Company not found or unauthorized'}), 404

# ================= CRUD RECORDS =================

@app.route('/api/companies/<int:company_id>/records', methods=['GET'])
@login_required
def get_records(company_id):
    records = database.get_records_by_company(company_id, session['user_id'])
    if records is None:
        return jsonify({'error': 'Company not found or unauthorized'}), 404
    return jsonify(records)

@app.route('/api/companies/<int:company_id>/records', methods=['POST'])
@login_required
def add_record(company_id):
    data = request.get_json()
    date = data.get('date')
    try:
        cash_flow = float(data.get('cash_flow', 0.0))
        profit = float(data.get('profit', 0.0))
        expenses = float(data.get('expenses', 0.0))
        loans = float(data.get('loans', 0.0)) # Added loans parameter
    except ValueError:
        return jsonify({'error': 'Financial values must be numeric'}), 400
        
    if not date:
        return jsonify({'error': 'Date is required'}), 400
        
    result = database.add_record(company_id, session['user_id'], date, cash_flow, profit, expenses, loans)
    if result is None:
        return jsonify({'error': 'Company not found or unauthorized'}), 404
    elif result == "UPDATED":
        return jsonify({'success': 'Financial record updated for this date'})
    
    # Return 201 Created (Fixed typo '21')
    return jsonify({'id': result, 'date': date, 'cash_flow': cash_flow, 'profit': profit, 'expenses': expenses, 'loans': loans}), 201

@app.route('/api/records/<int:record_id>', methods=['PUT'])
@login_required
def update_record(record_id):
    data = request.get_json()
    date = data.get('date')
    try:
        cash_flow = float(data.get('cash_flow', 0.0))
        profit = float(data.get('profit', 0.0))
        expenses = float(data.get('expenses', 0.0))
        loans = float(data.get('loans', 0.0)) # Added loans parameter
    except ValueError:
        return jsonify({'error': 'Financial values must be numeric'}), 400
        
    if not date:
        return jsonify({'error': 'Date is required'}), 400
        
    success = database.update_record(record_id, session['user_id'], date, cash_flow, profit, expenses, loans)
    if success:
        return jsonify({'success': 'Record updated successfully'})
    return jsonify({'error': 'Record not found, unauthorized, or date conflict'}), 400

@app.route('/api/records/<int:record_id>', methods=['DELETE'])
@login_required
def delete_record(record_id):
    success = database.delete_record(record_id, session['user_id'])
    if success:
        return jsonify({'success': 'Record deleted successfully'})
    return jsonify({'error': 'Record not found or unauthorized'}), 404

# ================= CSV IMPORT TO DB =================

def parse_csv(df):
    col_map = {}
    normalized_cols = {col.lower().replace(' ', '').replace('_', ''): col for col in df.columns}
    
    for k, v in normalized_cols.items():
        if 'date' in k or 'month' in k or 'period' in k:
            col_map['date'] = v
            break
    for k, v in normalized_cols.items():
        if 'cashflow' in k or 'cash' in k:
            col_map['cash_flow'] = v
            break
    for k, v in normalized_cols.items():
        if 'profit' in k or 'netincome' in k or 'revenue' in k:
            col_map['profit'] = v
            break
    for k, v in normalized_cols.items():
        if 'expense' in k or 'spending' in k or 'cost' in k:
            col_map['expenses'] = v
            break
    # Add loans check
    for k, v in normalized_cols.items():
        if 'loan' in k or 'debt' in k or 'liability' in k:
            col_map['loans'] = v
            break
            
    expected = ['date', 'cash_flow', 'profit', 'expenses']
    for exp in expected:
        if exp not in col_map:
            for col in df.columns:
                if col.lower() == exp:
                    col_map[exp] = col
                    break
    return col_map

@app.route('/api/companies/<int:company_id>/upload', methods=['POST'])
@login_required
def upload_data_file(company_id):
    if not database.verify_company_ownership(company_id, session['user_id']):
        return jsonify({'error': 'Company not found or unauthorized'}), 404
        
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
        
    # Check file size before reading (3MB limit)
    if request.content_length and request.content_length > 3 * 1024 * 1024:
        return jsonify({'error': 'File exceeds the 3MB limit.'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
        
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    
    try:
        df = None
        if ext == 'csv':
            df = pd.read_csv(file)
        elif ext in ['xls', 'xlsx']:
            df = pd.read_excel(file)
        elif ext == 'pdf':
            # PDF parsing strategy: Try to extract a table using pdfplumber
            pdf_bytes = file.read()
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                tables = []
                for page in pdf.pages:
                    extracted = page.extract_table()
                    if extracted:
                        tables.extend(extracted)
                if not tables:
                    return jsonify({'error': 'No readable tables found in PDF.'}), 400
                
                # Assume first row is header
                df = pd.DataFrame(tables[1:], columns=tables[0])
        else:
            return jsonify({'error': f'Unsupported file format: {ext}'}), 400
            
        col_map = parse_csv(df)
        
        required_cols = ['date', 'cash_flow', 'profit', 'expenses']
        missing = [col for col in required_cols if col not in col_map]
        if missing:
            return jsonify({
                'error': f"Failed to map columns automatically. Missing: {missing}. Found cols: {list(df.columns)}"
            }), 400
            
        has_loans = 'loans' in col_map
        cols_to_extract = [col_map[c] for c in required_cols]
        if has_loans:
            cols_to_extract.append(col_map['loans'])
            
        df_clean = df[cols_to_extract].copy()
        df_clean.columns = required_cols + (['loans'] if has_loans else [])
        
        df_clean['date'] = pd.to_datetime(df_clean['date'], errors='coerce').dt.strftime('%Y-%m-%d')
        # Remove commas and currency symbols for string columns in PDF extractions before numeric parsing
        for col in ['cash_flow', 'profit', 'expenses', 'loans']:
            if col in df_clean.columns and df_clean[col].dtype == object:
                df_clean[col] = df_clean[col].astype(str).str.replace(r'[^\d.-]', '', regex=True)
                
        df_clean['cash_flow'] = pd.to_numeric(df_clean['cash_flow'], errors='coerce')
        df_clean['profit'] = pd.to_numeric(df_clean['profit'], errors='coerce')
        df_clean['expenses'] = pd.to_numeric(df_clean['expenses'], errors='coerce')
        if 'loans' in df_clean.columns:
            df_clean['loans'] = pd.to_numeric(df_clean['loans'], errors='coerce').fillna(0.0)
        else:
            df_clean['loans'] = 0.0
            
        df_clean = df_clean.dropna(subset=required_cols)
        if len(df_clean) == 0:
            return jsonify({'error': 'No valid financial rows extracted after parsing.'}), 400
            
        import_count = 0
        for _, row in df_clean.iterrows():
            result = database.add_record(
                company_id=company_id,
                user_id=session['user_id'],
                date=row['date'],
                cash_flow=row['cash_flow'],
                profit=row['profit'],
                expenses=row['expenses'],
                loans=row['loans']
            )
            if result:
                import_count += 1
                
        return jsonify({'message': f'Successfully extracted and uploaded {import_count} records.'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ================= YEARLY SUMMARY GENERATOR =================

def generate_yearly_summaries(df_historical, df_predicted):
    df_historical['date'] = pd.to_datetime(df_historical['date'])
    df_predicted['date'] = pd.to_datetime(df_predicted['date'])
    
    df_historical['year'] = df_historical['date'].dt.year
    df_predicted['year'] = df_predicted['date'].dt.year
    
    summaries = []
    
    # 1. Historical Summaries
    for year, group in df_historical.groupby('year'):
        avg_cash = group['cash_flow'].mean()
        total_profit = group['profit'].sum()
        total_expenses = group['expenses'].sum()
        
        first_cash = group['cash_flow'].iloc[0]
        last_cash = group['cash_flow'].iloc[-1]
        
        if first_cash > 0 and last_cash < first_cash * 0.7:
            trend = f"Decline detected. Cash flow dropped by {((first_cash - last_cash)/first_cash)*100:.0f}% over the year."
        elif first_cash > 0 and last_cash > first_cash * 1.15:
            trend = f"Growth observed. Cash reserves increased by {((last_cash - first_cash)/first_cash)*100:.0f}% over the year."
        else:
            trend = "Stable. Reserves remained within safety margins."
            
        summaries.append({
            'year': str(year),
            'type': 'Historical',
            'text': f"Average cash flow was ${avg_cash:,.0f} with total profits of ${total_profit:,.0f} and expenses of ${total_expenses:,.0f}. {trend}"
        })
        
    # 2. Predicted Summaries
    last_hist_cash = df_historical['cash_flow'].iloc[-1]
    for year, group in df_predicted.groupby('year'):
        avg_cash = group['cash_flow'].mean()
        min_cash = group['cash_flow'].min()
        
        if min_cash == 0:
            trend = "AI predicts severe risk of insolvency, with cash reserves fully depleting to $0."
        elif min_cash < 15000:
            trend = "AI predicts high liquidity risk, with cash flow falling below the safety margin."
        elif last_hist_cash > 0 and avg_cash < last_hist_cash * 0.6:
            trend = "AI predicts a severe downward trend in cash flow compared to historical performance."
        else:
            trend = "AI predicts stable cash flow levels will continue."
            
        summaries.append({
            'year': str(year),
            'type': 'Forecasted',
            'text': f"Predicted average cash flow of ${avg_cash:,.0f}. {trend}"
        })
        
    return summaries

# ================= FORECASTING ENDPOINT =================

@app.route('/api/companies/<int:company_id>/forecast', methods=['POST'])
@login_required
def run_forecast(company_id):
    if not database.verify_company_ownership(company_id, session['user_id']):
        return jsonify({'error': 'Company not found or unauthorized'}), 404
        
    custom_url = ""
    raw_text = ""
    if request.is_json:
        req_data = request.get_json()
        if req_data:
            custom_url = req_data.get('custom_url', '')
            raw_text = req_data.get('raw_text', '')
            
    # Get records from DB
    records = database.get_records_by_company(company_id, session['user_id'])
    has_sufficient_data = records and len(records) >= 12
    has_nlp_context = bool(custom_url or raw_text)
    
    if not has_sufficient_data and not has_nlp_context:
        return jsonify({'error': f'Insufficient data. The model requires at least 12 months of historical data, but this company has only {len(records) if records else 0} months stored. Please provide CSV data or an AI Fine-Tuning Context URL.'}), 400
        
    import web_scraper
    
    historical_dates = []
    historical_cash = []
    historical_profit = []
    historical_expenses = []
    historical_loans = []
    predicted_dates_str = []
    predictions_clean = []
    alerts = []
    yearly_summaries = []
    
    if has_sufficient_data:
        # Load model and scaler
        if not os.path.exists(MODEL_PATH) or not os.path.exists(SCALER_PATH):
            return jsonify({'error': 'AI Model is not trained. Please run training script.'}), 500
            
        try:
            model, scaler = load_resources(MODEL_PATH, SCALER_PATH)
            
            # Format database records for scaling
            df = pd.DataFrame(records)
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date').reset_index(drop=True)
            
            historical_dates = df['date'].dt.strftime('%Y-%m-%d').tolist()
            historical_cash = df['cash_flow'].tolist()
            historical_profit = df['profit'].tolist()
            historical_expenses = df['expenses'].tolist()
            historical_loans = df['loans'].tolist() if 'loans' in df.columns else [0.0]*len(df)
            
            # Prepare sequence of last 12 months (features: cash_flow, profit, expenses, loans)
            # Ensure loans is in the dataframe, otherwise default to 0
            if 'loans' not in df.columns:
                df['loans'] = 0.0
            last_12_features = df.tail(12)[['cash_flow', 'profit', 'expenses', 'loans']].values
            last_12_scaled = scaler.transform(last_12_features)
            
            # Predict 12 months recursively
            predictions = predict_future(model, scaler, last_12_scaled, num_months=12, pad_with_last=True)
            
            # Generate predicted dates
            last_date = df['date'].iloc[-1]
            predicted_dates = pd.date_range(start=last_date + pd.DateOffset(months=1), periods=12, freq='ME')
            predicted_dates_str = predicted_dates.strftime('%Y-%m-%d').tolist()
            
            # Cap cash flow prediction at zero
            predictions_clean = [max(0.0, float(val)) for val in predictions]
            
            # Distress analysis
            last_historical_cash = float(df['cash_flow'].iloc[-1])
            alerts = detect_financial_distress(np.array(predictions_clean), last_historical_cash)
            
            # Generate yearly summaries
            df_pred = pd.DataFrame({
                'date': pd.to_datetime(predicted_dates_str),
                'cash_flow': predictions_clean
            })
            yearly_summaries = generate_yearly_summaries(df.copy(), df_pred)
            
        except Exception as e:
            return jsonify({'error': f'Prediction failed: {str(e)}'}), 500
    else:
        # NLP ONLY MODE
        alerts = [{
            'status': 'WARNING',
            'message': 'NOTICE: Insufficient CSV data. Results are based purely on Web Intelligence and NLP Context.'
        }]
        import datetime
        today = datetime.date.today()
        # Mock empty data so UI doesn't crash
        historical_dates = [(today - datetime.timedelta(days=30)).strftime('%Y-%m-%d')]
        historical_cash = [0]
        historical_profit = [0]
        historical_expenses = [0]
        historical_loans = [0]
        predicted_dates_str = [today.strftime('%Y-%m-%d')]
        predictions_clean = [0]
        
    try:
        
        # Get company details (including CA notes)
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT name, ca_notes FROM companies WHERE id = ?', (company_id,))
        row = cursor.fetchone()
        company_name = row['name']
        ca_notes = row['ca_notes']
        conn.close()
        
        # --- SILENT WEB SCRAPER INTEGRATION ---
        web_data = web_scraper.gather_company_web_data(company_name)
        web_summary = None
        web_trend = None
        
        if web_data:
            web_summary = web_data['summary']
            web_trend = web_data['trend']
            risk_adj = web_data['risk_adjustment']
            
            # Modify AI alerts based on real-world stock risk
            if risk_adj >= 2:
                alerts.insert(0, {
                    'status': 'CRITICAL',
                    'message': f'CRITICAL: Web Intelligence Alert. Stock has plummeted recently! {web_trend}'
                })
            elif risk_adj == 1:
                alerts.insert(0, {
                    'status': 'WARNING',
                    'message': f'WARNING: Web Intelligence Alert. Stock is down recently. {web_trend}'
                })
            elif risk_adj < 0 and len(alerts) > 0 and alerts[0]['status'] != 'STABLE':
                # If model predicted risk but stock is up, we can mitigate it slightly or just note it
                alerts.insert(0, {
                    'status': 'WARNING', # Override critical to warning if stock is actually doing well
                    'message': f'NOTICE: Internal metrics show risk, but real-world stock is performing well ({web_trend}).'
                })
                
        # --- WIKIPEDIA HISTORY INTEGRATION ---
        history_timeline = web_scraper.get_company_history_timeline(company_name)
        
        # --- CUSTOM NLP FINE-TUNING ---
        nlp_sentiment = None
        if custom_url or raw_text:
            combined_text = raw_text + " "
            
            if custom_url:
                scraped_text = web_scraper.scrape_custom_url(custom_url)
                if not scraped_text or len(scraped_text) < 50:
                    alerts.insert(0, {
                        'status': 'WARNING',
                        'message': 'NOTICE: Failed to extract text from the provided URL (likely blocked by anti-bot security). Please paste the article directly into the Raw Text box.'
                    })
                else:
                    combined_text += scraped_text
                
            nlp_sentiment = web_scraper.analyze_nlp_sentiment(combined_text)
            
            if nlp_sentiment['label'] == 'Distress / Negative':
                alerts.insert(0, {
                    'status': 'CRITICAL',
                    'message': f'CRITICAL: NLP Analysis on provided data shows severe distress (Score: {nlp_sentiment["score"]}).'
                })
            elif nlp_sentiment['label'] == 'Growth / Positive':
                if len(alerts) > 0 and alerts[0]['status'] != 'STABLE':
                    alerts.insert(0, {
                        'status': 'WARNING',
                        'message': f'NOTICE: Provided data shows positive sentiment ({nlp_sentiment["score"]}), mitigating risk.'
                    })
        
        response = {
            'company': company_name,
            'ca_notes': ca_notes, # Return CA Notes in forecast response
            'historical': {
                'dates': historical_dates,
                'cash_flow': historical_cash,
                'profit': historical_profit,
                'expenses': historical_expenses,
                'loans': historical_loans
            },
            'predictions': {
                'dates': predicted_dates_str,
                'cash_flow': predictions_clean
            },
            'alerts': alerts,
            'yearly_summaries': yearly_summaries,
            'history_timeline': history_timeline
        }
        
        # Save calculated data to DB
        score = 0
        status = 'Unknown'
        if alerts and len(alerts) > 0:
            status = alerts[0].get('status', 'Unknown')
            if status == 'STABLE':
                score = 85.0
            elif status == 'WARNING':
                score = 45.0
            elif status == 'CRITICAL':
                score = 15.0
                
        database.update_company_forecast(company_id, session['user_id'], score, status, web_summary, web_trend)
        
        return jsonify(response)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Processing failed: {str(e)}'}), 500



if __name__ == '__main__':
    os.makedirs('templates', exist_ok=True)
    app.run(debug=True, port=5000)
