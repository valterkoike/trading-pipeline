terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.0"
    }
  }
}

variable "aws_profile" {
  description = "The AWS CLI SSO profile name to use for deployment"
  type        = string
}

variable "subscriber_email" {
  description = "The email address to receive trading signals"
  type        = string
}

provider "aws" {
  region  = "us-east-2"
  profile = var.aws_profile
}

data "aws_region" "current" {}

locals {
  src_hash = substr(sha256(join("", [
    filesha256("${path.module}/src/ingestor.py"),
    filesha256("${path.module}/src/analyzer.py"),
    filesha256("${path.module}/src/publisher.py"),
    filesha256("${path.module}/src/aggregator.py"),
    filesha256("${path.module}/src/api_handler.py"),
    filesha256("${path.module}/src/requirements.txt"),
    filesha256("${path.module}/src/Dockerfile")
  ])), 0, 8)
}

# ==========================================
# --- STEP 1: STORAGE, ECR, & INGESTOR ---
# ==========================================

resource "random_id" "suffix" {
  byte_length = 4
}

resource "aws_s3_bucket" "data_lake" {
  bucket        = "trading-data-lake-${random_id.suffix.hex}"
  force_destroy = true
}

resource "aws_ecr_repository" "repo" {
  name                 = "trading-pipeline-ingestor"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
}

resource "aws_ecr_lifecycle_policy" "cleanup_old_versions" {
  repository = aws_ecr_repository.repo.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep only the last 3 images to save storage"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 3
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

resource "null_resource" "docker_build_push" {
  triggers = {
    src_hash = local.src_hash
  }

  provisioner "local-exec" {
    interpreter = ["cmd", "/C"]
    
    command = <<-EOF
      aws ecr get-login-password --region ${data.aws_region.current.name} --profile ${var.aws_profile} | docker login --username AWS --password-stdin ${split("/", aws_ecr_repository.repo.repository_url)[0]} && docker build --platform linux/amd64 --provenance=false -t ${aws_ecr_repository.repo.repository_url}:${local.src_hash} ./src && docker push ${aws_ecr_repository.repo.repository_url}:${local.src_hash}
    EOF
  }
}

# Shared Lambda IAM Role
data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda_exec" {
  name               = "ingestor_lambda_docker_role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_policy" "s3_write" {
  name = "lambda_s3_write_policy"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "s3:PutObject",
          "s3:GetObject"
        ]
        Effect   = "Allow"
        Resource = "${aws_s3_bucket.data_lake.arn}/*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "attach_s3_write" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = aws_iam_policy.s3_write.arn
}

resource "aws_lambda_function" "ingestor" {
  depends_on    = [null_resource.docker_build_push]
  function_name = "market_data_ingestor"
  role          = aws_iam_role.lambda_exec.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.repo.repository_url}:${local.src_hash}"
  timeout       = 300
  memory_size   = 512
  
  environment {
    variables = {
      BUCKET_NAME = aws_s3_bucket.data_lake.bucket
    }
  }
}

# ==========================================
# --- STEP 2: ANALYZER ---
# ==========================================

resource "aws_lambda_function" "analyzer" {
  depends_on    = [null_resource.docker_build_push]
  function_name = "market_data_analyzer"
  role          = aws_iam_role.lambda_exec.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.repo.repository_url}:${local.src_hash}"
  timeout       = 300 
  memory_size   = 3008

  image_config {
    command = ["analyzer.handler"] 
  }

  environment {
    variables = {
      BUCKET_NAME = aws_s3_bucket.data_lake.bucket
    }
  }
}

# ==========================================
# --- STEP 3: PUBLISHER, AGGREGATOR, DYNAMO, & SNS ---
# ==========================================

resource "aws_dynamodb_table" "signals" {
  name         = "TradingSignals"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "Symbol"
  range_key    = "Date"

  attribute {
    name = "Symbol"
    type = "S"
  }
  attribute {
    name = "Date"
    type = "S"
  }
}

resource "aws_sns_topic" "alerts" {
  name = "trading-signals-topic"
}

resource "aws_sns_topic_subscription" "email_sub" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.subscriber_email
}

resource "aws_lambda_function" "publisher" {
  depends_on    = [null_resource.docker_build_push]
  function_name = "market_data_publisher"
  role          = aws_iam_role.lambda_exec.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.repo.repository_url}:${local.src_hash}"
  timeout       = 30

  image_config {
    command = ["publisher.handler"] 
  }

  environment {
    variables = {
      DYNAMO_TABLE = aws_dynamodb_table.signals.name
      SNS_TOPIC    = aws_sns_topic.alerts.arn
    }
  }
}

resource "aws_lambda_function" "aggregator" {
  depends_on    = [null_resource.docker_build_push]
  function_name = "market_data_aggregator"
  role          = aws_iam_role.lambda_exec.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.repo.repository_url}:${local.src_hash}"
  timeout       = 30

  image_config {
    command = ["aggregator.handler"] 
  }
  environment {
    variables = {
      SNS_TOPIC = aws_sns_topic.alerts.arn
      DYNAMO_TABLE = aws_dynamodb_table.signals.name
    }
  }
}

resource "aws_iam_policy" "dynamo_sns_policy" {
  name = "lambda_dynamo_sns_policy"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action   = [
          "dynamodb:PutItem", 
          "dynamodb:Scan", 
          "dynamodb:DeleteItem", 
          "dynamodb:BatchWriteItem"
        ]
        Effect   = "Allow"
        Resource = aws_dynamodb_table.signals.arn
      },
      {
        Action   = ["sns:Publish"]
        Effect   = "Allow"
        Resource = aws_sns_topic.alerts.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "attach_dynamo_sns" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = aws_iam_policy.dynamo_sns_policy.arn
}

# ==========================================
# --- STEP FUNCTIONS (THE WORKFLOW) ---
# ==========================================

data "aws_iam_policy_document" "sfn_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["states.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "sfn_exec" {
  name               = "trading_pipeline_sfn_role"
  assume_role_policy = data.aws_iam_policy_document.sfn_assume_role.json
}

resource "aws_iam_policy" "sfn_invoke_lambdas_policy" {
  name = "sfn_invoke_all_lambdas_policy"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action   = ["lambda:InvokeFunction"]
        Effect   = "Allow"
        Resource = [
          aws_lambda_function.ingestor.arn,
          aws_lambda_function.analyzer.arn,
          aws_lambda_function.publisher.arn,
          aws_lambda_function.aggregator.arn
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "attach_sfn_invoke_all" {
  role       = aws_iam_role.sfn_exec.name
  policy_arn = aws_iam_policy.sfn_invoke_lambdas_policy.arn
}

resource "aws_sfn_state_machine" "trading_pipeline" {
  name     = "TradingDataPipeline"
  role_arn = aws_iam_role.sfn_exec.arn

  definition = jsonencode({
    Comment = "Parallel processing pipeline with final aggregation"
    StartAt = "ProcessAllStocks"
    States = {
      ProcessAllStocks = {
        Type = "Map"
        ItemsPath = "$.symbols"
        MaxConcurrency = 10
        Parameters = {
          "symbol.$" = "$$.Map.Item.Value"
        }
        Iterator = {
          StartAt = "IngestMarketData"
          States = {
            IngestMarketData = {
              Type       = "Task"
              Resource   = aws_lambda_function.ingestor.arn
              Next       = "AnalyzeMarketData"
              ResultPath = "$.ingestion_result"
            }
            AnalyzeMarketData = {
              Type       = "Task"
              Resource   = aws_lambda_function.analyzer.arn
              Next       = "PublishSignal"
            }
            PublishSignal = {
              Type       = "Task"
              Resource   = aws_lambda_function.publisher.arn
              End        = true
            }
          }
        }
        Next = "AggregateAndNotify"
      }
      AggregateAndNotify = {
        Type     = "Task"
        Resource = aws_lambda_function.aggregator.arn
        End      = true
      }
    }
  })
}

# ==========================================
# --- STEP 4: EVENTBRIDGE AUTOMATION ---
# ==========================================

resource "aws_iam_role" "eventbridge_sfn_role" {
  name = "eventbridge_sfn_invoke_role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "eventbridge_sfn_policy" {
  name = "eventbridge_sfn_invoke_policy"
  role = aws_iam_role.eventbridge_sfn_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action   = "states:StartExecution"
        Effect   = "Allow"
        Resource = aws_sfn_state_machine.trading_pipeline.arn
      }
    ]
  })
}

resource "aws_cloudwatch_event_rule" "market_close" {
  name                = "trigger-trading-pipeline-market-close"
  description         = "Triggers Step Function every weekday at 6:00 PM EST"
  schedule_expression = "cron(0 23 ? * MON-FRI *)"
}

# tell EventBridge what to trigger and what payload to pass
resource "aws_cloudwatch_event_target" "sfn_target" {
  rule      = aws_cloudwatch_event_rule.market_close.name
  target_id = "TradingPipelineTarget"
  arn       = aws_sfn_state_machine.trading_pipeline.arn
  role_arn  = aws_iam_role.eventbridge_sfn_role.arn

  input = file("${path.module}/symbols.json")
}

# ==========================================
# --- STEP 5: API GATEWAY & DASHBOARD ---
# ==========================================

# 1. API Handler Lambda
resource "aws_lambda_function" "api_handler" {
  depends_on    = [null_resource.docker_build_push]
  function_name = "market_data_api_handler"
  role          = aws_iam_role.lambda_exec.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.repo.repository_url}:${local.src_hash}"
  timeout       = 30

  image_config {
    command = ["api_handler.handler"]
  }

  environment {
    variables = {
      DYNAMO_TABLE = aws_dynamodb_table.signals.name
      BUCKET_NAME  = aws_s3_bucket.data_lake.bucket
    }
  }
}

# Grant read permissions on DynamoDB for the API Handler
resource "aws_iam_policy" "dynamo_read_policy" {
  name = "lambda_dynamo_read_policy"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action   = ["dynamodb:Scan", "dynamodb:Query", "dynamodb:GetItem"]
        Effect   = "Allow"
        Resource = aws_dynamodb_table.signals.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "attach_dynamo_read" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = aws_iam_policy.dynamo_read_policy.arn
}

# 2. HTTP API Gateway
resource "aws_apigatewayv2_api" "http_api" {
  name          = "trading-dashboard-api"
  protocol_type = "HTTP"
  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "OPTIONS"]
    allow_headers = ["*"]
  }
}

resource "aws_apigatewayv2_stage" "default_stage" {
  api_id      = aws_apigatewayv2_api.http_api.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_apigatewayv2_integration" "lambda_integration" {
  api_id                 = aws_apigatewayv2_api.http_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api_handler.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "get_signals" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "GET /signals"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_integration.id}"
}

resource "aws_lambda_permission" "api_gateway_permission" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api_handler.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http_api.execution_arn}/*/*"
}

# ==========================================
# --- OUTPUTS ---
# ==========================================

output "api_endpoint" {
  value       = "${aws_apigatewayv2_api.http_api.api_endpoint}/signals"
  description = "Paste this URL into your React frontend to fetch data."
}
