import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import {
  Fn,
  IgnoreMode,
  aws_ec2 as ec2,
  aws_ecr_assets as ecrAssets,
  aws_ecs as ecs,
  aws_iam as iam,
  aws_logs as logs,
  aws_s3 as s3,
} from "aws-cdk-lib";
import { Construct } from "constructs";

const REPO_ROOT = fileURLToPath(new URL("../../", import.meta.url));
const DOCKERFILE = "api/Dockerfile";
const DOCKER_IGNORE = fileURLToPath(new URL("../../api/Dockerfile.dockerignore", import.meta.url));
const API_PORT = 8000;
// Express Mode routes to the container named Main with one named TCP port.
const CONTAINER_NAME = "Main";
const EXPRESS_POLICY = "service-role/AmazonECSInfrastructureRoleforExpressGatewayServices";
const CPU_UNITS = 1024;
const MEMORY_MIB = 2048;
const SCALE_CPU_PERCENT = 60;
const SUBNET_COUNT = 2;
const CONTENT_DIR_IN_IMAGE = "/app/content";
// ponytail: the default 1 GiB chunk cache is too large beside 4 worker threads in 2 GB.
const CHUNK_CACHE_BYTES = 512 * 1024 * 1024;

export type Architecture = "arm64" | "x86_64";

export interface ApiServiceProps {
  readonly dataBucket: s3.IBucket;
  readonly logGroup: logs.ILogGroup;
  readonly architecture: Architecture;
  readonly maxTasks: number;
}

/** The analysis API on ECS Express Mode with a task definition of our own (DES-005). */
export class ApiService extends Construct {
  readonly service: ecs.CfnExpressGatewayService;
  /** Host name of the Express endpoint, for the CloudFront origin. */
  readonly domain: string;

  constructor(scope: Construct, id: string, props: ApiServiceProps) {
    super(scope, id);
    const isArm = props.architecture === "arm64";
    const image = new ecrAssets.DockerImageAsset(this, "Image", {
      directory: REPO_ROOT,
      file: DOCKERFILE,
      platform: isArm ? ecrAssets.Platform.LINUX_ARM64 : ecrAssets.Platform.LINUX_AMD64,
      exclude: readIgnoreLines(DOCKER_IGNORE),
      ignoreMode: IgnoreMode.DOCKER,
    });

    const taskRole = new iam.Role(this, "TaskRole", {
      assumedBy: new iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
      description: "BORAMAE API task: reads and writes the data bucket",
    });
    // POWER is read anonymously over HTTPS (api/boramae/power/reader.py): no grant.
    // No Bedrock grant: production runs with the LLM off (D-04, D-12).
    taskRole.addToPolicy(
      new iam.PolicyStatement({
        actions: ["s3:GetObject", "s3:PutObject"],
        resources: [props.dataBucket.arnForObjects("*")],
      }),
    );
    taskRole.addToPolicy(
      new iam.PolicyStatement({
        actions: ["s3:ListBucket"],
        resources: [props.dataBucket.bucketArn],
      }),
    );

    const task = new ecs.FargateTaskDefinition(this, "Task", {
      cpu: CPU_UNITS,
      memoryLimitMiB: MEMORY_MIB,
      runtimePlatform: {
        cpuArchitecture: isArm ? ecs.CpuArchitecture.ARM64 : ecs.CpuArchitecture.X86_64,
        operatingSystemFamily: ecs.OperatingSystemFamily.LINUX,
      },
      taskRole,
    });
    task.addContainer(CONTAINER_NAME, {
      containerName: CONTAINER_NAME,
      image: ecs.ContainerImage.fromDockerImageAsset(image),
      portMappings: [{ containerPort: API_PORT, name: "http", protocol: ecs.Protocol.TCP }],
      logging: ecs.LogDrivers.awsLogs({ logGroup: props.logGroup, streamPrefix: "ecs" }),
      // Only fields of api/boramae/config.py: load_settings raises on any other name.
      environment: {
        BORAMAE_STORE_URL: `s3://${props.dataBucket.bucketName}`,
        BORAMAE_LLM_ENABLED: "false",
        BORAMAE_AWS_REGION: "us-west-2",
        BORAMAE_CONTENT_DIR: CONTENT_DIR_IN_IMAGE,
        BORAMAE_CHUNK_CACHE_BYTES: String(CHUNK_CACHE_BYTES),
        BORAMAE_COMPUTE_LOCATION: "us-west-2",
      },
    });

    const infrastructureRole = new iam.Role(this, "InfrastructureRole", {
      assumedBy: new iam.ServicePrincipal("ecs.amazonaws.com"),
      description: "Lets ECS manage the load balancer and scaling of the BORAMAE API",
      managedPolicies: [iam.ManagedPolicy.fromAwsManagedPolicyName(EXPRESS_POLICY)],
    });

    const vpc = ec2.Vpc.fromLookup(this, "DefaultVpc", { isDefault: true });
    const subnets = vpc
      .selectSubnets({ subnetType: ec2.SubnetType.PUBLIC, onePerAz: true })
      .subnetIds.slice(0, SUBNET_COUNT);

    // With taskDefinitionArn, Express reads CPU, memory, roles and the container from
    // the task definition; the API forbids setting them on the service as well.
    this.service = new ecs.CfnExpressGatewayService(this, "Service", {
      serviceName: "boramae-api",
      infrastructureRoleArn: infrastructureRole.roleArn,
      taskDefinitionArn: task.taskDefinitionArn,
      healthCheckPath: "/health",
      networkConfiguration: { subnets },
      scalingTarget: {
        minTaskCount: 1,
        maxTaskCount: props.maxTasks,
        autoScalingMetric: "AVERAGE_CPU",
        autoScalingTargetValue: SCALE_CPU_PERCENT,
      },
    });
    // The role policies are separate resources; the first task needs them in place.
    this.service.node.addDependency(taskRole, task.obtainExecutionRole());

    // Endpoint reads https://<name>.ecs.<region>.on.aws/ in the docs; this keeps only
    // the host whether or not the attribute carries the scheme and the slash.
    const withoutScheme = Fn.join("", Fn.split("https://", this.service.attrEndpoint));
    this.domain = Fn.select(0, Fn.split("/", withoutScheme));
  }
}

function readIgnoreLines(path: string): string[] {
  return readFileSync(path, "utf8")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line !== "" && !line.startsWith("#"));
}
