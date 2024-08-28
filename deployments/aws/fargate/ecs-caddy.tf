# ECS Task Definition for Caddy Service
resource "aws_ecs_task_definition" "caddy_task_definition" {
  family                   = "TracecatCaddyTaskDefinition"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.caddy_execution.arn
  task_role_arn            = aws_iam_role.caddy_task.arn

  container_definitions = jsonencode([
    {
      name  = "TracecatCaddyContainer"
      image = "caddy:2.8.4-alpine"
      portMappings = [
        {
          containerPort = 80
          hostPort      = 80
          name          = "caddy"
          appProtocol   = "http"
        }
      ]
      command = [
        "/bin/sh",
        "-c",
        <<EOT
cat <<EOF > /etc/caddy/Caddyfile
:80 {
  handle_path /api* {
    reverse_proxy http://api-service:8000
  }
  reverse_proxy http://ui-service:3000
}
EOF
caddy run --config /etc/caddy/Caddyfile
EOT
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.tracecat_log_group.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "caddy"
        }
      }
      dockerPullConfig = {
        maxAttempts = 3
        backoffTime = 10
      }
    }
  ])
}

resource "aws_ecs_service" "tracecat_caddy" {
  name            = "tracecat-caddy"
  cluster         = aws_ecs_cluster.tracecat_cluster.id
  task_definition = aws_ecs_task_definition.caddy_task_definition.arn
  launch_type     = "FARGATE"
  desired_count   = 1

  network_configuration {
    subnets         = aws_subnet.private[*].id
    security_groups = [
      aws_security_group.caddy.id,
      aws_security_group.core.id
    ]
  }

  service_connect_configuration {
    enabled   = true
    namespace = local.local_dns_namespace
    
    service {
      port_name      = "caddy"
      discovery_name = "caddy-service"
      client_alias {
        port     = 80
        dns_name = "caddy-service"
      }
    }

    log_configuration {
      log_driver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.tracecat_log_group.name
        awslogs-region        = var.aws_region 
        awslogs-stream-prefix = "service-connect-caddy"
      }
    }
  }

  load_balancer {
    target_group_arn = aws_alb_target_group.caddy.id
    container_name   = "TracecatCaddyContainer"
    container_port   = 80
  }

  depends_on = [
    aws_ecs_service.tracecat_api,
    aws_ecs_service.tracecat_ui
  ]
}