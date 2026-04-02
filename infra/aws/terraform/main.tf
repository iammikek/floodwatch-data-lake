terraform {
  required_version = ">= 1.4.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

resource "aws_s3_bucket" "curated" {
  bucket = "${var.project_name}-curated"
}

resource "aws_s3_bucket_versioning" "curated" {
  bucket = aws_s3_bucket.curated.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "curated" {
  bucket                  = aws_s3_bucket.curated.id
  block_public_acls       = true
  block_public_policy     = false
  ignore_public_acls      = true
  restrict_public_buckets = false
}

resource "aws_s3_bucket" "raw" {
  bucket = "${var.project_name}-raw"
}

resource "aws_s3_bucket_public_access_block" "raw" {
  bucket                  = aws_s3_bucket.raw.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_cloudfront_origin_access_control" "oac" {
  name                              = "${var.project_name}-oac"
  description                       = var.project_name
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "cdn" {
  enabled             = true
  comment             = "${var.project_name}-cdn"
  price_class         = "PriceClass_100"
  default_root_object = ""

  origin {
    domain_name = aws_s3_bucket.curated.bucket_regional_domain_name
    origin_id   = "s3-curated"
    s3_origin_config {
      origin_access_identity = ""
    }
    origin_access_control_id = aws_cloudfront_origin_access_control.oac.id
  }

  default_cache_behavior {
    target_origin_id       = "s3-curated"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD", "OPTIONS"]
    compress               = true
    forwarded_values {
      query_string = true
      cookies {
        forward = "none"
      }
      headers = []
    }
    min_ttl     = 0
    default_ttl = 300
    max_ttl     = 3600
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
      locations        = []
    }
  }

  viewer_certificate {
    acm_certificate_arn            = var.acm_certificate_arn
    ssl_support_method             = "sni-only"
    minimum_protocol_version       = "TLSv1.2_2021"
    cloudfront_default_certificate = false
  }

  aliases = [var.cdn_domain_name]
}

data "aws_iam_policy_document" "curated_policy" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    actions = ["s3:GetObject"]
    resources = [
      "${aws_s3_bucket.curated.arn}/*"
    ]
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.cdn.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "curated" {
  bucket = aws_s3_bucket.curated.id
  policy = data.aws_iam_policy_document.curated_policy.json
}

resource "aws_ecr_repository" "api" {
  name = "${var.project_name}-api"
  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_repository" "worker" {
  name = "${var.project_name}-worker"
  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_iam_role" "apprunner_ecr" {
  name               = "${var.project_name}-apprunner-ecr"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "build.apprunner.amazonaws.com" }, Action = "sts:AssumeRole" }, { Effect = "Allow", Principal = { Service = "tasks.apprunner.amazonaws.com" }, Action = "sts:AssumeRole" }] })
}

resource "aws_iam_role_policy_attachment" "apprunner_ecr_attach" {
  role       = aws_iam_role.apprunner_ecr.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
}

resource "aws_apprunner_service" "api" {
  service_name = "${var.project_name}-api"

  source_configuration {
    authentication_configuration {
      access_role_arn = aws_iam_role.apprunner_ecr.arn
    }
    image_repository {
      image_identifier      = var.api_image_identifier
      image_repository_type = "ECR"
      image_configuration {
        port = "8000"
        runtime_environment_variables = {
          REMOTE_BASE_URL = "https://${var.cdn_domain_name}/ea"
          POLYGONS_TTL    = "300"
          WARNINGS_TTL    = "120"
          MEASUREMENTS_TTL = "60"
          RL_LIMIT        = "60"
          RL_WINDOW_S     = "60"
          PORT            = "8000"
        }
        command = ["bash", "-lc", "/app/scripts/start-api.sh"]
      }
    }
    auto_deployments_enabled = true
  }

  instance_configuration {
    cpu    = "1024"
    memory = "2048"
  }

  health_check_configuration {
    path                = "/healthz"
    protocol            = "HTTP"
    interval            = 5
    timeout             = 2
    healthy_threshold   = 1
    unhealthy_threshold = 3
  }
}

resource "aws_ecs_cluster" "worker" {
  name = "${var.project_name}-cluster"
}

resource "aws_iam_role" "ecs_task_execution" {
  name               = "${var.project_name}-ecs-exec"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }] })
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_attach" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "ecs_task_role" {
  name               = "${var.project_name}-ecs-task"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }] })
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/${var.project_name}-worker"
  retention_in_days = 14
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "${var.project_name}-worker"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "1024"
  memory                   = "2048"
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn
  container_definitions    = jsonencode([{
    name      = "worker"
    image     = var.worker_image_identifier
    essential = true
    command   = ["bash", "-lc", "python -m ingestion.cli backfill-ea-region --region SOM --parameters level,flow --exclude-qualifiers Tidal Level --from 2026-02 --to 2026-03 --resume"]
    environment = []
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.worker.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "ecs"
      }
    }
  }])
}

resource "aws_iam_role" "events_run_task" {
  name               = "${var.project_name}-events-run-task"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "events.amazonaws.com" }, Action = "sts:AssumeRole" }] })
}

data "aws_iam_policy_document" "events_run_task_policy" {
  statement {
    effect = "Allow"
    actions = [
      "ecs:RunTask",
      "iam:PassRole"
    ]
    resources = [
      aws_ecs_task_definition.worker.arn
    ]
  }
}

resource "aws_iam_policy" "events_run_task" {
  name   = "${var.project_name}-events-run-task"
  policy = data.aws_iam_policy_document.events_run_task_policy.json
}

resource "aws_iam_role_policy_attachment" "events_run_task_attach" {
  role       = aws_iam_role.events_run_task.name
  policy_arn = aws_iam_policy.events_run_task.arn
}

resource "aws_cloudwatch_event_rule" "worker_schedule" {
  name                = "${var.project_name}-worker-schedule"
  schedule_expression = var.worker_schedule_expression
}

resource "aws_cloudwatch_event_target" "worker_target" {
  rule      = aws_cloudwatch_event_rule.worker_schedule.name
  target_id = "ecs-run-task"
  arn       = aws_ecs_cluster.worker.arn
  role_arn  = aws_iam_role.events_run_task.arn

  ecs_target {
    task_definition_arn = aws_ecs_task_definition.worker.arn
    task_count          = 1
    launch_type         = "FARGATE"
    network_configuration {
      subnets         = var.private_subnet_ids
      security_groups = [var.ecs_security_group_id]
      assign_public_ip = "DISABLED"
    }
  }
}

output "s3_curated_bucket" {
  value = aws_s3_bucket.curated.id
}

output "s3_raw_bucket" {
  value = aws_s3_bucket.raw.id
}

output "cloudfront_domain_name" {
  value = aws_cloudfront_distribution.cdn.domain_name
}

output "apprunner_service_url" {
  value = aws_apprunner_service.api.service_url
}
