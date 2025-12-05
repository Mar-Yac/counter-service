data "aws_iam_policy_document" "csi_driver_trust_policy" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [module.eks.oidc_provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "${module.eks.oidc_provider}:sub"
      values   = ["system:serviceaccount:kube-system:secrets-store-csi-driver"]
    }
  }
}

resource "aws_iam_role" "csi_driver_role" {
  name               = "csi-driver-secrets-role"
  assume_role_policy = data.aws_iam_policy_document.csi_driver_trust_policy.json
}

resource "aws_iam_role_policy_attachment" "csi_driver_secrets_policy" {
  role       = aws_iam_role.csi_driver_role.name
  policy_arn = "arn:aws:iam::aws:policy/SecretsManagerReadWrite" # Or a more restrictive custom policy
}

data "aws_iam_policy_document" "counter_service_trust_policy" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [module.eks.oidc_provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "${module.eks.oidc_provider}:sub"
      values   = ["system:serviceaccount:prod:counter-service"] # Service Account in 'prod' namespace
    }
  }
}

resource "aws_iam_role" "counter_service_secrets_role" {
  name               = "counter-service-secrets-role"
  assume_role_policy = data.aws_iam_policy_document.counter_service_trust_policy.json
}

resource "aws_iam_role_policy_attachment" "counter_service_secrets_policy" {
  role       = aws_iam_role.counter_service_secrets_role.name
  policy_arn = "arn:aws:iam::aws:policy/SecretsManagerReadWrite"
}

data "aws_iam_policy_document" "grafana_trust_policy" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [module.eks.oidc_provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "${module.eks.oidc_provider}:sub"
      values   = ["system:serviceaccount:monitoring:grafana"] # Service Account in 'monitoring' namespace
    }
  }
}

resource "aws_iam_role" "grafana_secrets_role" {
  name               = "grafana-secrets-role"
  assume_role_policy = data.aws_iam_policy_document.grafana_trust_policy.json
}

resource "aws_iam_role_policy_attachment" "grafana_secrets_policy" {
  role       = aws_iam_role.grafana_secrets_role.name
  policy_arn = "arn:aws:iam::aws:policy/SecretsManagerReadWrite"
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = "nano-counter-eks"
  cluster_version = "1.34"

  cluster_endpoint_public_access = true

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  access_entries = {
    admin-user = {
      principal_arn = "arn:aws:iam::630943284793:user/Yacov.Marsha@gmail.com"
      policy_associations = {
        admin = {
          policy_arn = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
          access_scope = {
            type = "cluster"
          }
        }
      }
    }
  }

  cluster_addons = {
    coredns = {
      most_recent = true
    }
    kube-proxy = {
      most_recent = true
    }
    vpc-cni = {
      most_recent = true
    }
    aws-ebs-csi-driver = {
      most_recent = true
    }
  }

  cluster_upgrade_policy = {
  support_type = "STANDARD"
  }

  eks_managed_node_groups = {
    main-ng = {
      min_size     = 3
      max_size     = 6
      desired_size = 3

      instance_types = ["t3.medium"]
      disk_size      = 20
      capacity_type  = "ON_DEMAND"

      subnet_ids = module.vpc.private_subnets

      block_device_mappings = {
        xvda = {
          device_name = "/dev/xvda"
          ebs = {
            volume_size           = 20
            volume_type           = "gp3"
            encrypted             = true
            delete_on_termination = true
          }
        }
      }

      # Attach the ECR read-only policy to the node group's IAM role
      iam_role_additional_policies = {
        ECRReadOnly = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
        # This policy is required for the EBS CSI Driver to function correctly.
        EBSCSIDriver = "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
      }
    }
  }

  enable_irsa = true
}
