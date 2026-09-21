import yfinance as yf
import pandas as pd
import boto3
import os
from datetime import datetime
from zoneinfo import ZoneInfo 

# Initialize the S3 client globally outside the handler.
# This takes advantage of Lambda "warm starts" to reuse the connection 
# across multiple invocations, which is especially useful during the 
# Step Functions parallel Map state where this runs concurrently.
s3_client = boto3.client('s3')
BUCKET_NAME = os.environ.get('BUCKET_NAME')

def handler(event, context):
    """
    Lambda entry point for the Ingestor Step.
    Expected 'event': A dictionary from the Step Function Map state 
    containing the 'symbol' to process (e.g., {"symbol": "AAPL"}).
    """
    symbol = event.get("symbol", "AAPL")
    
    # Lock the timezone to US Eastern Time (New York).
    # Since US stock markets operate in Eastern Time, this ensures that data pulled 
    # right after market close gets saved under the correct calendar date folder, 
    # avoiding UTC midnight rollover inconsistencies.
    eastern = ZoneInfo("America/New_York")
    ts0 = datetime.now(eastern).strftime("%Y-%m-%d")
    
    print(f"Downloading historical data for {symbol} on {ts0}...")
    
    try:
        # Fetch the maximum available daily historical data from Yahoo Finance
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="max")
        
        # Guard clause: If the symbol is invalid or delisted, yfinance returns an empty DataFrame
        if df.empty:
            print(f"No data found for {symbol}, skipping.")
            return {
                "statusCode": 404,
                "symbol_processed": symbol,
                "message": "No data found"
            }

        # ---------------------------------------------------------
        # DATA CLEANING & STANDARDIZATION
        # ---------------------------------------------------------
        df['Symbol'] = symbol
        # yfinance puts the Date in the index. Extract it and format it as a compact 
        # string (YYYYMMDD) to save space and ensure easy parsing downstream.
        df['Date'] = pd.to_datetime(df.index).strftime('%Y%m%d')
        
        # Drop unnecessary columns
        columns_to_drop = ['Dividends', 'Stock Splits', 'Capital Gains']
        for col in columns_to_drop:
            if col in df.columns:
                df = df.drop(columns=[col])
                
        df = df.reset_index(drop=True)
        
        # ---------------------------------------------------------
        # FILE EXPORT & S3 UPLOAD
        # ---------------------------------------------------------
        # AWS Lambda provides a temporary scratch space at '/tmp/' (up to 512MB default).
        # write the CSV to tmp before uploading to S3.
        tmp_file_path = f"/tmp/{symbol}.csv"
        
        # Enforce a strict column order so the Analyzer Lambda always knows what to expect
        df.to_csv(tmp_file_path, index=False, header=True, 
                  columns=["Symbol", "Date", "Open", "High", "Low", "Close", "Volume"])
        
        # Create a logical, date-partitioned folder structure in the S3 Data Lake
        # e.g., raw_data/2023-10-24/AAPL.csv
        s3_key = f"raw_data/{ts0}/{symbol}.csv"
        
        print(f"Uploading {symbol}.csv to s3://{BUCKET_NAME}/{s3_key}")
        s3_client.upload_file(tmp_file_path, BUCKET_NAME, s3_key)
        
    except Exception as e:
        print(f"Error processing {symbol}: {str(e)}")
        # Return a failure gracefully so the Step Function knows this specific branch failed
        return {
            "statusCode": 500,
            "symbol_processed": symbol,
            "error": str(e)
        }

    # Return the exact S3 path where the data was saved.
    # The Step Function maps this output to 'ingestion_result' and passes it 
    # directly into the Analyzer Lambda so it knows where to find the file.
    return {
        "statusCode": 200,
        "bucket": BUCKET_NAME,
        "data_path": f"raw_data/{ts0}/",
        "symbol_processed": symbol
    }