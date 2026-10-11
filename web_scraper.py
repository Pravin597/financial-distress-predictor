import yfinance as yf
import requests
import wikipedia
import re
from bs4 import BeautifulSoup
from textblob import TextBlob
import wikipedia
import re

wikipedia.set_user_agent("FinancialDistressPredictor/1.0")

def search_ticker(company_name):
    """
    Silently search Yahoo Finance for the best matching stock ticker
    for a given company name.
    """
    url = f"https://query2.finance.yahoo.com/v1/finance/search?q={company_name}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        data = response.json()
        quotes = data.get('quotes', [])
        for q in quotes:
            # Look for an equity symbol
            if 'symbol' in q and q.get('quoteType') in ['EQUITY', 'ETF']:
                return q['symbol']
    except Exception as e:
        print(f"Error searching ticker for {company_name}: {e}")
    return None

def gather_company_web_data(company_name):
    """
    Gathers real-world data for a company to adjust the AI prediction.
    Returns:
        dict: {'summary': str, 'trend': str, 'risk_adjustment': int}
        Returns None if it's a private company (no ticker found).
    """
    ticker_symbol = search_ticker(company_name)
    if not ticker_symbol:
        return None
        
    try:
        ticker = yf.Ticker(ticker_symbol)
        
        # Get business summary
        info = ticker.info
        summary = info.get('longBusinessSummary', 'No summary available.')
        if len(summary) > 200:
            summary = summary[:197] + "..."
            
        # Get 6-month stock history
        hist = ticker.history(period="6mo")
        if hist.empty or len(hist) < 2:
            return None
            
        start_price = hist['Close'].iloc[0]
        end_price = hist['Close'].iloc[-1]
        
        # Calculate trend
        change_pct = ((end_price - start_price) / start_price) * 100
        
        trend_str = f"Ticker: {ticker_symbol} | Current Price: ${end_price:.2f} | 6-Month Trend: {change_pct:+.2f}%"
        
        # Determine risk adjustment
        # If stock crashed > 20%, we add heavy risk
        # If stock crashed 5-20%, mild risk
        # If stock is up > 10%, we reduce risk
        risk_adjustment = 0
        if change_pct < -20:
            risk_adjustment = 2  # Critical risk adder
        elif change_pct < -5:
            risk_adjustment = 1  # Warning risk adder
        elif change_pct > 10:
            risk_adjustment = -1 # Safe risk reducer
            
        return {
            'summary': summary,
            'trend': trend_str,
            'risk_adjustment': risk_adjustment,
            'ticker': ticker_symbol
        }
        
    except Exception as e:
        print(f"Error fetching yfinance data for {ticker_symbol}: {e}")
        return None

def get_company_history_timeline(company_name):
    """
    Scrapes Wikipedia for the company and extracts a timeline of major growth/fault events.
    """
    try:
        # Search and load Wikipedia page
        search_results = wikipedia.search(company_name)
        if not search_results:
            return []
            
        try:
            page = wikipedia.page(search_results[0], auto_suggest=False)
        except wikipedia.exceptions.DisambiguationError as e:
            page = wikipedia.page(e.options[0], auto_suggest=False)
            
        content = page.content
        
        # Split into sentences roughly
        sentences = re.split(r'(?<=[.!?])\s+', content)
        
        fault_keywords = ['fall', 'drop', 'loss', 'bankrupt', 'debt', 'fail', 'scandal', 'crash', 'crisis', 'decline', 'decrease', 'resign', 'lawsuit', 'fired']
        growth_keywords = ['grow', 'profit', 'acquire', 'record', 'launch', 'success', 'surge', 'increase', 'expand', 'peak', 'highest', 'bought', 'milestone']
        
        timeline_events = {}
        
        for sentence in sentences:
            # Look for a year (1900-2099)
            year_match = re.search(r'\b(19\d{2}|20\d{2})\b', sentence)
            if year_match:
                year = year_match.group(1)
                sentence_lower = sentence.lower()
                
                # Determine impact
                impact = 'Neutral'
                if any(kw in sentence_lower for kw in fault_keywords):
                    impact = 'Fault/Decline'
                elif any(kw in sentence_lower for kw in growth_keywords):
                    impact = 'Growth/Success'
                    
                if impact != 'Neutral':
                    # Clean up sentence (remove newlines, weird characters)
                    clean_sent = sentence.replace('\n', ' ').strip()
                    if len(clean_sent) > 15 and len(clean_sent) < 300:
                        # Only keep the first significant event found for a year to avoid clutter
                        if year not in timeline_events:
                            timeline_events[year] = {
                                'year': year,
                                'impact': impact,
                                'event': clean_sent
                            }
                            
        # Sort chronologically
        sorted_events = sorted(timeline_events.values(), key=lambda x: int(x['year']))
        
        # Keep the most recent/important ones (last 10 events)
        return sorted_events[-10:]
        
    except Exception as e:
        print(f"Error fetching historical timeline for {company_name}: {e}")
        return []

def scrape_custom_url(url):
    """
    Scrapes the main text content of a given URL using BeautifulSoup4.
    """
    if not url or not url.startswith('http'):
        return ""
        
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1'
        }
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return ""
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove scripts, styles, headers, footers
        for element in soup(["script", "style", "header", "footer", "nav", "aside"]):
            element.decompose()
            
        # Get text from paragraphs
        paragraphs = soup.find_all('p')
        text = " ".join([p.get_text() for p in paragraphs])
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Return at most 5000 characters to prevent NLP overflow
        return text[:5000]
    except Exception as e:
        print(f"Error scraping URL {url}: {e}")
        return ""

def analyze_nlp_sentiment(text):
    """
    Uses TextBlob combined with a custom financial lexicon to analyze the sentiment.
    """
    if not text or len(text.strip()) < 10:
        return {'score': 0.0, 'label': 'Neutral'}
        
    try:
        blob = TextBlob(text)
        base_score = blob.sentiment.polarity
        
        # TextBlob is weak on financial terms like "bankruptcy" or "lawsuit".
        # We manually adjust the score using a custom lexicon.
        text_lower = text.lower()
        
        distress_keywords = ['bankrupt', 'lawsuit', 'fraud', 'crash', 'collapse', 'plummet', 'fired', 'scandal', 'debt', 'loss', 'fail', 'liquidation', 'insolvent']
        growth_keywords = ['record profit', 'surge', 'all time high', 'massive growth', 'success', 'expansion', 'acquisition', 'breakthrough', 'lucrative']
        
        distress_count = sum(1 for kw in distress_keywords if kw in text_lower)
        growth_count = sum(1 for kw in growth_keywords if kw in text_lower)
        
        # Adjust score heavily based on financial keywords
        sentiment_score = base_score + (growth_count * 0.2) - (distress_count * 0.25)
        
        # Clamp score between -1.0 and 1.0
        sentiment_score = max(-1.0, min(1.0, sentiment_score))
        
        if sentiment_score <= -0.15:
            label = 'Distress / Negative'
        elif sentiment_score >= 0.15:
            label = 'Growth / Positive'
        else:
            label = 'Neutral'
            
        return {
            'score': round(sentiment_score, 3),
            'label': label,
            'subjectivity': round(blob.sentiment.subjectivity, 3)
        }
    except Exception as e:
        print(f"Error in NLP sentiment analysis: {e}")
        return {'score': 0.0, 'label': 'Neutral'}
