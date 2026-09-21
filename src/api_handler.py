import os
import boto3
import json

# Initialize AWS clients globally outside the handler.
# This leverages Lambda's "warm starts", reusing the connection pool 
# for subsequent API calls and reducing latency.
dynamodb = boto3.resource('dynamodb')
s3_client = boto3.client('s3')

# Retrieve backend configuration from environment variables (set by Terraform)
table_name = os.environ.get('DYNAMO_TABLE')
bucket_name = os.environ.get('BUCKET_NAME')

def handler(event, context):
    """
    Lambda entry point for the API Gateway integration.
    This function acts as the backend for the frontend dashboard, retrieving
    saved trading signals and securely serving the associated chart images.
    """
    table = dynamodb.Table(table_name)
    
    try:
        # Retrieve all trading signals from the DynamoDB table.
        # the Aggregator Lambda ensures this table never exceeds 100 items.
        response = table.scan()
        items = response.get('Items', [])
        
        # Iterate through the retrieved records to format them for the frontend
        for item in items:
            chart_location = item.get('ChartImageURL', 'None')
            
            # If the database record contains a raw S3 URI (e.g., s3://my-bucket/charts/...),
            # convert it into a standard HTTP URL that a web browser can render.
            if chart_location and chart_location != 'None' and chart_location.startswith('s3://'):
                
                # Strip the "s3://bucket-name/" prefix to isolate the exact file path (the S3 Key)
                s3_key = chart_location.replace(f"s3://{bucket_name}/", "")
                
                # The S3 bucket is private, so the frontend cannot access the image directly.
                # dynamically generate a temporary, signed URL.
                # ExpiresIn=3600 means 1 hour
                presigned_url = s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': bucket_name, 'Key': s3_key},
                    ExpiresIn=3600
                )
                
                # Overwrite the raw S3 URI in the response dictionary with the clickable web link
                item['ChartImageURL'] = presigned_url

        # Return a formatted HTTP response to the API Gateway
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                # CORS (Cross-Origin Resource Sharing) headers are strictly required.
                # Without these, web browsers will block the frontend React/Vue app from reading this data.
                "Access-Control-Allow-Origin": "*", 
                "Access-Control-Allow-Methods": "GET,OPTIONS"
            },
            # Serialize the Python dictionary into a JSON string for the HTTP body
            "body": json.dumps(items)
        }

    except Exception as e:
        # Catch and log the exact error to CloudWatch for debugging
        print(f"Error reading DynamoDB or generating S3 URLs: {str(e)}")
        
        # Return a standard HTTP 500 Internal Server Error to the client gracefully,
        # ensuring CORS headers are still included so the frontend can read the error state.
        return {
            "statusCode": 500,
            "headers": {
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({"error": str(e)})
        }