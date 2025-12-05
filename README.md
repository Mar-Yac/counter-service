# Counter Service

## 1. Overview

This project provides a containerized web service that counts requests. It is designed for deployment on AWS EKS and includes a complete infrastructure-as-code setup, a CI/CD pipeline, and implementations for high availability, persistence, security, and observability.

The core application is a Python Flask service that exposes two primary endpoints:
- `POST /`: Increments a counter.
- `GET /`: Retrieves the current value of the counter.

## 2. Features

- **Infrastructure as Code**: The entire AWS infrastructure (VPC, EKS Cluster) is managed by Terraform.
- **Containerization**: The application is containerized using a multi-stage, slim, non-root Docker image.
- **CI/CD**: A GitHub Actions pipeline automates building, testing, and pushing the Docker image to Amazon ECR.
- **GitOps Deployment**: The pipeline triggers deployments by updating a Helm chart in the Git repository, which is then synced to the cluster by a GitOps operator like Argo CD.
- **High Availability**: The service is deployed with multiple replicas across different Availability Zones, managed by a Horizontal Pod Autoscaler (HPA) and a Pod Disruption Budget (PDB).
- **Persistence**: The counter's state is persisted in a Redis instance, which is deployed as a highly available StatefulSet with encrypted persistent storage.
- **Security**: Implements modern security best practices, including IAM Roles for Service Accounts (IRSA), encrypted storage, non-root containers, and secure secrets management.
- **Observability**: Provides structured logging, Prometheus metrics, and OpenTelemetry tracing for comprehensive monitoring.
- **Network & Ingress**: Uses Envoy as a service proxy, fronted by an AWS Network Load Balancer (NLB) for ingress traffic, and includes application-level rate limiting.

## 3. Architecture

The architecture consists of the following key components:

1.  **AWS Infrastructure**:
    *   A VPC with public and private subnets across three Availability Zones in `eu-west-2`.
    *   An EKS (Elastic Kubernetes Service) cluster with a managed node group.
    *   An ECR (Elastic Container Registry) to store Docker images.
    *   An NLB (Network Load Balancer) to expose the service to the internet.
    *   AWS Secrets Manager for storing application secrets.

2.  **Kubernetes Cluster**:
    *   **Counter Service**: The main application deployment.
    *   **Envoy Proxy**: A deployment that acts as the ingress gateway, routing external traffic to the counter service.
    *   **Redis**: A StatefulSet for persisting the counter data.
    *   **Monitoring Stack**: Includes Prometheus for metrics collection and Grafana for visualization (deployed via the `kube-prometheus-stack` Helm chart).
    *   **Secrets Management**: The `aws-secrets-store-csi-driver` is used to securely mount secrets from AWS Secrets Manager into pods.

## 4. Prerequisites

Before you begin, ensure you have the following tools installed and configured:
- `aws-cli`
- `terraform`
- `kubectl`
- `helm`

You will also need an AWS account with appropriate permissions and a GitHub account with a forked copy of this repository.

## 5. Deployment Guide

### Step 1: Configure Environment Variables

This project uses placeholders for account-specific identifiers. You must replace them before deployment.

- **`<ACCOUNT_ID>`**: Your AWS Account ID.
  - File: `.github/workflows/ci-cd.yaml`
  - File: `helm/counter-service/values.yaml`
- **`<GITHUB_ORG>/<GITHUB_REPO>`**: Your GitHub organization and repository name.
  - This is required for the IAM Role trust policy for GitHub Actions.

### Step 2: Provision the Infrastructure

The Terraform code in the `infra/` directory defines the VPC and EKS cluster.

```sh
cd infra/
terraform init
terraform apply
```

Once the process is complete, configure `kubectl` to connect to your new EKS cluster:

```sh
aws eks update-kubeconfig --name nano-counter-eks --region eu-west-2
```

### Step 3: Set Up CI/CD and Secrets

1.  **Create ECR Repository**:
    ```sh
    aws ecr create-repository \
      --repository-name counter-service \
      --region eu-west-2 \
      --image-scanning-configuration scanOnPush=true
    ```

2.  **Create IAM Role for GitHub Actions**: The CI/CD pipeline requires an IAM role to push images to ECR. Create an IAM role with a trust relationship to the GitHub OIDC provider and attach the `AmazonEC2ContainerRegistryPowerUser` policy.

3.  **Create Secrets in AWS Secrets Manager**: Create a secret in AWS Secrets Manager to store the Redis password. The application expects a secret with a key named `password`. Update the `secretArn` in `helm/counter-service/values.yaml` with the ARN of the secret you create.

4.  **Create IAM Role for the Application**: The application's Service Account needs permission to read secrets from AWS Secrets Manager. Create an IAM role with the `secretsmanager:GetSecretValue` permission and a trust relationship with the EKS OIDC provider. Update the `serviceAccount.annotations` in `helm/counter-service/values.yaml` with the ARN of this role.

### Step 4: Deploy the Application using GitOps

This project is designed for a GitOps workflow.

1.  **Install a GitOps Operator**: Install a tool like **Argo CD** or **Flux** in your cluster. For Argo CD, you can follow the official "Getting Started" guide.

2.  **Configure the Operator**: Create an `Application` resource in your GitOps tool that points to the `helm/counter-service` directory in your Git repository.

Once configured, the GitOps operator will automatically sync the Helm chart and deploy all the necessary resources, including the counter-service, Redis, Envoy, and the monitoring stack.

## 6. How to Test the Service

1.  **Get the Service URL**: Find the public URL of the Network Load Balancer.
    ```sh
    kubectl get svc envoy-proxy -n prod -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'
    ```

2.  **Interact with the Service**:
    ```sh
    # Increment the counter
    curl -X POST http://<NLB_HOSTNAME>/

    # Get the current count
    curl http://<NLB_HOSTNAME>/
    ```

## 7. Design and Configuration Notes

### Persistence
- **Method**: Redis is used for persistence, deployed via the Bitnami Helm chart. This provides a scalable, shared state for the counter.
- **Encryption**: All persistent volumes use the `encrypted-gp3` StorageClass, ensuring data at rest is encrypted via AWS KMS.

### High Availability
- **HPA**: A Horizontal Pod Autoscaler scales the application from 2 to 10 replicas based on CPU utilization.
- **Multi-AZ**: The EKS cluster, node groups, and application pods are distributed across three Availability Zones for resilience.
- **PDB**: A Pod Disruption Budget ensures a minimum number of pods are available during voluntary disruptions like node upgrades.

### Security
- **Secrets**: The `aws-secrets-store-csi-driver` securely mounts secrets from AWS Secrets Manager into the application pods. Image pull secrets are handled by assigning an IAM role to the EKS nodes.
- **Container**: The Docker image is minimal, runs as a non-root user, and has a read-only root filesystem.
- **Network**: The application is not directly exposed to the internet. Traffic is routed through an Envoy proxy, and rate limiting is enforced at the application level.

### Observability
- **Logging**: The application produces structured (JSON) logs, which can be easily ingested by log aggregation systems.
- **Metrics**: A `/metrics` endpoint is exposed for Prometheus scraping. Key metrics include request counts, latency, and Redis connection status.
- **Tracing**: OpenTelemetry is integrated to provide distributed tracing capabilities.
