import os
import boto3

# Initialize the AWS resource AND the table reference outside the handler.
# This takes advantage of Lambda "warm starts" to reuse the network connection 
# across multiple invocations, reducing latency and execution time.
dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get('DYNAMO_TABLE')
table = dynamodb.Table(table_name)

def handler(event, context):
    """
    Lambda entry point for the Publisher Step.
    This function takes the processed analysis from the Analyzer Lambda and 
    persists actionable trading signals to a DynamoDB table for the frontend dashboard.
    """
    
    # Extract data from the Step Functions event payload. 
    # This payload is exactly what the Analyzer Lambda returned.
    symbol = event.get('symbol', 'UNKNOWN')
    date = event.get('date', 'UNKNOWN')
    signal = event.get('signal', '')
    close_price = event.get('close_price', '0.0')
    chart_url = event.get('chart_url', 'None')
    
    # ---------------------------------------------------------
    # CONDITIONAL DATABASE WRITES
    # ---------------------------------------------------------
    # Only write to the database if a definitive buy/sell signal was actually generated.
    # If the Analyzer returned an empty string for the signal (meaning no action to take),
    # skip writing to DynamoDB. This significantly saves Write Capacity Units (WCUs) and storage costs.
    if signal:
        try:
            # Persist the record to DynamoDB.
            # Based on the Terraform setup, 'Symbol' acts as the Partition Key (Hash)
            # and 'Date' acts as the Sort Key (Range).
            table.put_item(
                Item={
                    'Symbol': symbol,
                    'Date': date,
                    'SignalType': signal,
                    'ClosePrice': str(close_price), # Stored as a string to avoid Float precision issues in DynamoDB
                    'ChartImageURL': chart_url
                }
            )
            print(f"Successfully wrote {symbol} record to DynamoDB.")
            
        except Exception as e:
            # Log the error to CloudWatch and re-raise it.
            # Raising the error ensures this specific Step Function task is marked as "Failed",
            # rather than silently failing and returning a false success.
            print(f"Failed to write to DynamoDB: {str(e)}")
            raise e
        
    # ---------------------------------------------------------
    # PIPELINE CONTINUATION
    # ---------------------------------------------------------
    # Return the data identically to how it was received. 
    # Because this Lambda is running inside a Step Functions 'Map' state, 
    # all these returned JSON objects will be collected into a single array 
    # and passed downstream to the final Aggregator Lambda.
    return {
        "statusCode": 200,
        "symbol": symbol,
        "signal": signal,
        "date": date,
        "close_price": close_price,
        "chart_url": chart_url
    }