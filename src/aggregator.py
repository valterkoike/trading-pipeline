import os
import boto3

# Initialize AWS clients globally outside the handler.
# This takes advantage of AWS Lambda execution environment reuse (warm starts),
# improving performance by not re-initializing the clients on every single invocation.
sns_client = boto3.client('sns')
s3_client = boto3.client('s3') 
dynamodb = boto3.resource('dynamodb')

# Retrieve configuration values from environment variables (typically set via Terraform)
topic_arn = os.environ.get('SNS_TOPIC')
table_name = os.environ.get('DYNAMO_TABLE')

def handler(event, context):
    """
    Main Lambda entry point.
    Expected 'event' payload: A list of dictionaries representing processed market data
    from the Step Function's parallel mapping phase.
    """
    print(f"Aggregator received payload with {len(event)} items.")
    
    # ---------------------------------------------------------
    # 1. EMAIL NOTIFICATION LOGIC
    # ---------------------------------------------------------
    # Filter the incoming data to only include items that actually generated a buy/sell signal.
    # Ignores items where the signal is None, empty, or a non-actionable status like "HOLD".
    actionable_signals = [item for item in event if item.get('signal')]
    
    if actionable_signals:
        # Extract the date from the first signal to use in the email header
        date = actionable_signals[0].get('date', 'Unknown')
        
        # Start constructing the plain-text email body
        email_body = f"SYSTEM TRADING SUMMARY: {date}\n"
        email_body += "="*50 + "\n\n"
        
        # Iterate through all actionable signals to append them to the email
        for s in actionable_signals:
            symbol = s.get('symbol', 'UNKNOWN')
            raw_s3_url = s.get('chart_url', '')
            
            clickable_link = "No chart available"
            
            # If a chart was successfully generated and saved to S3
            if raw_s3_url.startswith("s3://"):
                try:
                    # Strip the "s3://" protocol prefix and split the remainder into exactly two parts:
                    # e.g., "my-bucket/path/to/chart.png" -> bucket="my-bucket", key="path/to/chart.png"
                    path_parts = raw_s3_url.replace("s3://", "").split("/", 1)
                    bucket, key = path_parts[0], path_parts[1]
                    
                    # S3 bucket is private, so generate a "Presigned URL".
                    # This gives anyone with the link temporary, secure access to view the chart image.
                    # ExpiresIn=86400 is 24 hours.
                    clickable_link = s3_client.generate_presigned_url(
                        'get_object', 
                        Params={'Bucket': bucket, 'Key': key}, 
                        ExpiresIn=86400
                    )
                except Exception as e:
                    print(f"Could not generate presigned URL for {symbol}: {e}")
                    # Fallback to the raw URL if presigning fails, even though it won't be clickable
                    clickable_link = raw_s3_url

            # Append the specific stock's data and the presigned chart link to the email body
            email_body += f"[{symbol}] : {s['signal']}\n"
            email_body += f"Close Price: ${s['close_price']}\n"
            email_body += f"Chart: {clickable_link}\n"
            email_body += "-"*50 + "\n"
            
        # Dispatch the compiled email via Amazon SNS to all subscribers (e.g., the user's email)
        sns_client.publish(
            TopicArn=topic_arn,
            Subject=f"Market Summary: {len(actionable_signals)} Signals on {date}",
            Message=email_body
        )
        print("Email summary sent.")

    # ---------------------------------------------------------
    # 2. DATABASE PRUNING LOGIC
    # ---------------------------------------------------------
    # To keep DynamoDB costs low and API response times fast, strictly limit 
    # the frontend dashboard's history to only the 100 most recent signals.
    try:
        table = dynamodb.Table(table_name)
        
        # scan() reads the entire table.  
        # table size is capped at 100 items.
        response = table.scan()
        all_items = response.get('Items', [])
        
        # Sort the items chronologically (newest dates first).
        # use a tuple (Date, Symbol) as the sorting key so that items on the same day 
        # are consistently sorted alphabetically.
        all_items.sort(key=lambda x: (x['Date'], x['Symbol']), reverse=True)
        
        # Slice the array to find items that fall outside our 100-item threshold.
        # all_items[0:99] are kept. all_items[100:] are targeted for deletion.
        items_to_delete = all_items[100:]
        
        if items_to_delete:
            # Use the DynamoDB batch_writer(). 
            # It automatically buffers requests and sends them in batches of 25 (the AWS limit),
            # making bulk deletions significantly faster and preventing throttling errors.
            with table.batch_writer() as batch:
                for item in items_to_delete:
                    batch.delete_item(
                        Key={
                            'Symbol': item['Symbol'],
                            'Date': item['Date']
                        }
                    )
            print(f"Pruned {len(items_to_delete)} old records from the database. Maintained top 100.")
        else:
            print("Database has fewer than 100 items. No pruning required.")
            
    except Exception as e:
        # Catch and log the error so the Lambda doesn't crash entirely if pruning fails.
        # return a 200 status since the email sent successfully.
        print(f"Failed to prune DynamoDB: {str(e)}")

    # Return standard HTTP response payload for the Step Function / invoker
    return {
        "statusCode": 200,
        "status": f"Processed {len(actionable_signals)} signals and verified database size."
    }