data "aws_iam_policy_document" "app_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

# Role the application's ECS tasks run as.
resource "aws_iam_role" "app" {
  name               = "acme-app-${var.env}"
  assume_role_policy = data.aws_iam_policy_document.app_assume.json
}

data "aws_iam_policy_document" "app_secrets" {
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = ["arn:aws:secretsmanager:${var.region}:*:secret:acme-app/${var.env}/*"]
  }
}

resource "aws_iam_role_policy" "app_secrets" {
  name   = "secrets"
  role   = aws_iam_role.app.id
  policy = data.aws_iam_policy_document.app_secrets.json
}
