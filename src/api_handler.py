import os
import boto3
import json

dynamodb = boto3.resource('dynamodb')
s3_client = boto3.client('s3')

table_name = os.environ.get('DYNAMO_TABLE')
bucket_name = os.environ.get('BUCKET_NAME')

def handler(event, context):
    table = dynamodb.Table(table_name)
    
    try:
        # Scan the DynamoDB table for all records
        response = table.scan()
        items = response.get('Items', [])
        
        # Transform items and generate pre-signed URLs for S3 images
        for item in items:
            chart_location = item.get('ChartImageURL', 'None')
            
            if chart_location and chart_location != 'None' and chart_location.startswith('s3://'):
                # Extract the object key from S3 URL
                s3_key = chart_location.replace(f"s3://{bucket_name}/", "")
                
                # Generate a temporary pre-signed URL (valid for 60 minutes)
                presigned_url = s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': bucket_name, 'Key': s3_key},
                    ExpiresIn=3600
                )
                item['ChartImageURL'] = presigned_url

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*", # Required for CORS
                "Access-Control-Allow-Methods": "GET,OPTIONS"
            },
            "body": json.dumps(items)
        }

    except Exception as e:
        print(f"Error reading DynamoDB or generating S3 URLs: {str(e)}")
        return {
            "statusCode": 500,
            "headers": {
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({"error": str(e)})
        }