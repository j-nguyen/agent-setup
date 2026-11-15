variable "region" {
  type    = string
  default = "us-east-1"
}

variable "env" {
  type        = string
  description = "Deployment environment: staging or prod."
}
