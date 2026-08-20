import os
import boto3

# Initialize clients globally
sns_client = boto3.client('sns')
s3_client = boto3.client('s3') 
dynamodb = boto3.resource('dynamodb')

topic_arn = os.environ.get('SNS_TOPIC')
table_name = os.environ.get('DYNAMO_TABLE')

def handler(event, context):
    print(f"Aggregator received payload with {len(event)} items.")
    
    # ---------------------------------------------------------
    # 1. EMAIL NOTIFICATION LOGIC
    # ---------------------------------------------------------
    actionable_signals = [item for item in event if item.get('signal')]
    
    if actionable_signals:
        date = actionable_signals[0].get('date', 'Unknown')
        email_body = f"SYSTEM TRADING SUMMARY: {date}\n"
        email_body += "="*50 + "\n\n"
        
        for s in actionable_signals:
            symbol = s.get('symbol', 'UNKNOWN')
            raw_s3_url = s.get('chart_url', '')
            
            clickable_link = "No chart available"
            if raw_s3_url.startswith("s3://"):
                try:
                    path_parts = raw_s3_url.replace("s3://", "").split("/", 1)
                    bucket, key = path_parts[0], path_parts[1]
                    clickable_link = s3_client.generate_presigned_url(
                        'get_object', Params={'Bucket': bucket, 'Key': key}, ExpiresIn=86400
                    )
                except Exception as e:
                    print(f"Could not generate presigned URL for {symbol}: {e}")
                    clickable_link = raw_s3_url

            email_body += f"[{symbol}] : {s['signal']}\n"
            email_body += f"Close Price: ${s['close_price']}\n"
            email_body += f"Chart: {clickable_link}\n"
            email_body += "-"*50 + "\n"
            
        sns_client.publish(
            TopicArn=topic_arn,
            Subject=f"Market Summary: {len(actionable_signals)} Signals on {date}",
            Message=email_body
        )
        print("Email summary sent.")

    # ---------------------------------------------------------
    # 2. DATABASE PRUNING LOGIC
    # ---------------------------------------------------------
    try:
        table = dynamodb.Table(table_name)
        
        # Scan the small table
        response = table.scan()
        all_items = response.get('Items', [])
        
        # Sort chronologically (newest first)
        all_items.sort(key=lambda x: (x['Date'], x['Symbol']), reverse=True)
        
        # Identify anything beyond the 100th item
        items_to_delete = all_items[100:]
        
        if items_to_delete:
            # Use batch_writer for efficient bulk deletions
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
        print(f"Failed to prune DynamoDB: {str(e)}")

    return {
        "statusCode": 200,
        "status": f"Processed {len(actionable_signals)} signals and verified database size."
    }