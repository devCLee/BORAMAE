import {
  CfnOutput,
  CfnParameter,
  RemovalPolicy,
  Stack,
  type StackProps,
  aws_budgets as budgets,
  aws_logs as logs,
  aws_s3 as s3,
  aws_secretsmanager as secretsmanager,
} from "aws-cdk-lib";
import type { Construct } from "constructs";

import { Edge } from "./edge.ts";
import { ApiService, type Architecture } from "./service.ts";

// ponytail: placeholders until TRD Q-22 fixes the rate values (requests per IP per 5 min).
const DEFAULT_RATE_PARSE = 100;
const DEFAULT_RATE_SPEC = 300;
const DEFAULT_MAX_TASKS = 2;
// Decision 3: with no CloudFront web ACL there is no rate limit, so one task at most.
const MAX_TASKS_WITHOUT_EDGE_ACL = 1;
const BUDGET_ALERT_PERCENT = 80;
const ORIGIN_HEADER_LENGTH = 32;
// The lowest limit that a WAFv2 rate-based rule accepts.
const MIN_RATE_LIMIT = 10;

// A wrong context value must fail at synth: it would otherwise fail at deploy time
// or silently select another path.
function oneOf<T extends string>(name: string, value: string, allowed: readonly T[]): T {
  const match = allowed.find((item) => item === value);
  if (match === undefined) {
    throw new Error(`context ${name} must be one of ${allowed.join(", ")}, not "${value}"`);
  }
  return match;
}

function rateLimit(name: string, value: string): number {
  const limit = Number(value);
  if (!Number.isInteger(limit) || limit < MIN_RATE_LIMIT) {
    throw new Error(`context ${name} must be an integer of at least ${MIN_RATE_LIMIT}, not "${value}"`);
  }
  return limit;
}

/**
 * The one BORAMAE stack (us-west-2): buckets, API service, edge, budget.
 *
 * Context: releaseId (web folder under releases/), rateLimitParse, rateLimitSpec,
 * edgeWaf (on | off; off is the decision 3 path), arch (arm64 | x86_64).
 * Parameters at deploy time: BudgetAmountUsd and BudgetAlertAddress.
 */
export class BoramaeStack extends Stack {
  constructor(scope: Construct, id: string, props: StackProps) {
    super(scope, id, props);
    const context = (name: string, fallback: string) =>
      String(this.node.tryGetContext(name) ?? fallback);
    const hasEdgeAcl = oneOf("edgeWaf", context("edgeWaf", "on"), ["on", "off"]) === "on";

    const bucketProps: s3.BucketProps = {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      // Versioning and the explicit private ACL answer two cfn-guard rules at no cost.
      versioned: true,
      accessControl: s3.BucketAccessControl.PRIVATE,
      removalPolicy: RemovalPolicy.RETAIN,
    };
    // Web: releases/<releaseId>/. Data: r/, grid/, meta/ and parse/ of the result store.
    const webBucket = new s3.Bucket(this, "WebBucket", bucketProps);
    const dataBucket = new s3.Bucket(this, "DataBucket", bucketProps);

    const logGroup = new logs.LogGroup(this, "ApiLogs", {
      // ponytail: TRD Q-27 is open; 3 months covers the judging window to Jan 27, 2027.
      retention: logs.RetentionDays.THREE_MONTHS,
      removalPolicy: RemovalPolicy.RETAIN,
    });

    const api = new ApiService(this, "Api", {
      dataBucket,
      logGroup,
      architecture: oneOf<Architecture>("arch", context("arch", "arm64"), ["arm64", "x86_64"]),
      maxTasks: hasEdgeAcl ? DEFAULT_MAX_TASKS : MAX_TASKS_WITHOUT_EDGE_ACL,
    });

    // Generated once and kept across deploys; only the template's dynamic references
    // read it, so the value never enters app code, the export or a tracked file.
    const originHeader = new secretsmanager.Secret(this, "OriginHeader", {
      description: "Value of the header that CloudFront sends to the BORAMAE API",
      generateSecretString: {
        excludePunctuation: true,
        passwordLength: ORIGIN_HEADER_LENGTH,
      },
    });

    const edge = new Edge(this, "Edge", {
      webBucket,
      releaseId: context("releaseId", "placeholder"),
      apiDomain: api.domain,
      apiLoadBalancerArn: api.service.attrEcsManagedResourceArnsIngressPathLoadBalancerArn,
      originHeaderValue: originHeader.secretValue.unsafeUnwrap(),
      rateLimits: hasEdgeAcl
        ? {
            parse: rateLimit("rateLimitParse", context("rateLimitParse", String(DEFAULT_RATE_PARSE))),
            spec: rateLimit("rateLimitSpec", context("rateLimitSpec", String(DEFAULT_RATE_SPEC))),
          }
        : undefined,
    });

    this.addBudget();

    const outputs: Record<string, string | undefined> = {
      PublicDomain: edge.distribution.distributionDomainName,
      DistributionId: edge.distribution.distributionId,
      WebBucketName: webBucket.bucketName,
      DataBucketName: dataBucket.bucketName,
      ApiServiceArn: api.service.attrServiceArn,
      ApiEndpoint: api.service.attrEndpoint,
      EdgeWebAclArn: edge.webAclArn,
    };
    for (const [name, value] of Object.entries(outputs)) {
      if (value !== undefined) new CfnOutput(this, name, { value });
    }
  }

  /** A monthly cost budget; amount and address come only as deploy parameters. */
  private addBudget(): void {
    const amount = new CfnParameter(this, "BudgetAmountUsd", {
      type: "Number",
      description: "Monthly cost budget in USD",
    });
    const address = new CfnParameter(this, "BudgetAlertAddress", {
      type: "String",
      noEcho: true,
      description: "E-mail address that receives the budget alert",
    });
    new budgets.CfnBudget(this, "MonthlyBudget", {
      budget: {
        budgetType: "COST",
        timeUnit: "MONTHLY",
        budgetLimit: { amount: amount.valueAsNumber, unit: "USD" },
      },
      notificationsWithSubscribers: [
        {
          notification: {
            notificationType: "ACTUAL",
            comparisonOperator: "GREATER_THAN",
            threshold: BUDGET_ALERT_PERCENT,
            thresholdType: "PERCENTAGE",
          },
          subscribers: [{ subscriptionType: "EMAIL", address: address.valueAsString }],
        },
      ],
    });
  }
}
