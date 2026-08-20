import yfinance as yf
import pandas as pd
import boto3
import os
from datetime import datetime
from zoneinfo import ZoneInfo 

s3_client = boto3.client('s3')
BUCKET_NAME = os.environ.get('BUCKET_NAME')

def handler(event, context):
    symbol = event.get("symbol", "AAPL")
    
    eastern = ZoneInfo("America/New_York")
    ts0 = datetime.now(eastern).strftime("%Y-%m-%d")
    
    print(f"Downloading historical data for {symbol} on {ts0}...")
    
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="max")
        
        if df.empty:
            print(f"No data found for {symbol}, skipping.")
            return {
                "statusCode": 404,
                "symbol_processed": symbol,
                "message": "No data found"
            }

        df['Symbol'] = symbol
        df['Date'] = pd.to_datetime(df.index).strftime('%Y%m%d')
        
        columns_to_drop = ['Dividends', 'Stock Splits', 'Capital Gains']
        for col in columns_to_drop:
            if col in df.columns:
                df = df.drop(columns=[col])
                
        df = df.reset_index(drop=True)
        
        tmp_file_path = f"/tmp/{symbol}.csv"
        df.to_csv(tmp_file_path, index=False, header=True, 
                  columns=["Symbol", "Date", "Open", "High", "Low", "Close", "Volume"])
        
        s3_key = f"raw_data/{ts0}/{symbol}.csv"
        
        print(f"Uploading {symbol}.csv to s3://{BUCKET_NAME}/{s3_key}")
        s3_client.upload_file(tmp_file_path, BUCKET_NAME, s3_key)
        
    except Exception as e:
        print(f"Error processing {symbol}: {str(e)}")
        return {
            "statusCode": 500,
            "symbol_processed": symbol,
            "error": str(e)
        }

    return {
        "statusCode": 200,
        "bucket": BUCKET_NAME,
        "data_path": f"raw_data/{ts0}/",
        "symbol_processed": symbol
    }