from diagrams import Diagram, Cluster, Edge
from diagrams.aws.compute import ECR
from diagrams.aws.network import NLB
from diagrams.aws.security import SecretsManager
from diagrams.k8s.controlplane import API
from diagrams.k8s.infra import Node
from diagrams.k8s.podconfig import Secret
from diagrams.k8s.compute import Pod
from diagrams.onprem.ci import GithubActions
from diagrams.onprem.vcs import Github
from diagrams.onprem.monitoring import Grafana, Prometheus
from diagrams.onprem.inmemory import Redis

# The 'direction' attribute sets the layout direction of the diagram. 'TB' means Top to Bottom.
with Diagram("Counter Service - Full Architecture", show=False, filename="project_architecture", direction="TB"):

    # Define external actors and entry points
    developer = Github("Developer")
    user_traffic = NLB("User Traffic (NLB)")

    # Define nodes within logical clusters
    with Cluster("CI/CD Pipeline"):
        github_repo = Github("GitHub Repo")
        github_actions = GithubActions("Build & Test")
        ecr = ECR("ECR Image Registry")
        # Define flow within the cluster
        github_repo >> github_actions >> ecr

    with Cluster("AWS Cloud"):
        secrets_manager = SecretsManager("Secrets Manager")

    with Cluster("AWS EKS Cluster"):
        api_server = API("API Server")
        argocd = GithubActions("ArgoCD") # Using GH Actions icon for GitOps tool

        with Cluster("App: counter-service (prod ns)"):
            counter_service = Pod("counter-service")
            # Using the proper Redis icon from the correct module
            redis_db = Redis("Redis")
            app_secret_provider = Node("SecretProviderClass (Redis)")
            redis_k8s_secret = Secret("redis-secret")

        with Cluster("App: monitoring (monitoring ns)"):
            prometheus = Prometheus("Prometheus")
            grafana = Grafana("Grafana")
            mon_secret_provider = Node("SecretProviderClass (Grafana)")
            grafana_k8s_secret = Secret("grafana-admin-credentials")

        with Cluster("Infra: csi-driver (kube-system ns)"):
            csi_driver = Node("AWS Secrets Store CSI Driver")

        # Define relationships within the EKS cluster
        api_server >> counter_service
        counter_service >> redis_db
        prometheus >> Edge(style="dashed", label="scrapes") >> counter_service
        prometheus >> grafana

        # Secrets flow within the cluster
        csi_driver >> app_secret_provider >> redis_k8s_secret
        csi_driver >> mon_secret_provider >> grafana_k8s_secret
        counter_service >> Edge(style="dashed", label="mounts") >> redis_k8s_secret
        grafana >> Edge(style="dashed", label="uses") >> grafana_k8s_secret

    # Define relationships between clusters and external actors
    developer >> github_repo
    github_repo >> Edge(style="dashed", label="monitors") >> argocd

    # ArgoCD deployment waves
    argocd >> Edge(label="Wave 0") >> csi_driver
    argocd >> Edge(label="Wave 1") >> grafana
    argocd >> Edge(label="Wave 2") >> counter_service

    user_traffic >> api_server
    secrets_manager >> Edge(style="dashed", label="fetches") >> csi_driver
