variable "aws_region" {
  type = string
}

variable "project_name" {
  type = string
}

variable "cdn_domain_name" {
  type = string
}

variable "acm_certificate_arn" {
  type = string
}

variable "api_image_identifier" {
  type = string
}

variable "worker_image_identifier" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "ecs_security_group_id" {
  type = string
}

variable "worker_schedule_expression" {
  type    = string
  default = "rate(1 day)"
}
