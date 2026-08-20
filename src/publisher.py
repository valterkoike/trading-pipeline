import os
import boto3

# Initialize the resource AND the table outside the handler for warm-start speed
dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get('DYNAMO_TABLE')
table = dynamodb.Table(table_name)

def handler(event, context):
    # Step Functions passes the output of analyzer.py directly in here
    symbol = event.get('symbol', 'UNKNOWN')
    date = event.get('date', 'UNKNOWN')
    signal = event.get('signal', '')
    close_price = event.get('close_price', '0.0')
    chart_url = event.get('chart_url', 'None')
    
    # Only write to the database if a buy/sell signal was actually generated
    if signal:
        try:
            table.put_item(
                Item={
                    'Symbol': symbol,
                    'Date': date,
                    'SignalType': signal,
                    'ClosePrice': str(close_price),
                    'ChartImageURL': chart_url
                }
            )
            print(f"Successfully wrote {symbol} record to DynamoDB.")
        except Exception as e:
            print(f"Failed to write to DynamoDB: {str(e)}")
            raise e
        
    # Return the data so Step Functions can pass it down to the Aggregator
    return {
        "statusCode": 200,
        "symbol": symbol,
        "signal": signal,
        "date": date,
        "close_price": close_price,
        "chart_url": chart_url
    }