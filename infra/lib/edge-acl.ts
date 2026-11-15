import { createHash } from "node:crypto";

import { Stack } from "aws-cdk-lib";
import {
  AwsCustomResource,
  AwsCustomResourcePolicy,
  PhysicalResourceId,
} from "aws-cdk-lib/custom-resources";
import { Construct } from "constructs";

// The CloudFront scope lives in us-east-1, where the Region SCP denies CloudFormation
// but allows WAFv2 (TODOS.md "Plan change: link first"), so the ACL is made by SDK call.
const EDGE_REGION = "us-east-1";
const SCOPE = "CLOUDFRONT";
const NAME_PREFIX = "boramae-edge-";
const RATE_WINDOW_S = 300;
const TOO_MANY_REQUESTS = 429;
const PARSE_PATH = "/api/v1/parse";
const SPEC_PATHS = ["/api/v1/trend", "/api/v1/caseboard", "/api/v1/scan"];
const MANAGED_GROUPS = [
  "AWSManagedRulesAmazonIpReputationList",
  "AWSManagedRulesCommonRuleSet",
  "AWSManagedRulesKnownBadInputsRuleSet",
];

export interface RateLimits {
  /** Requests per client IP per 5 minutes on POST /api/v1/parse. */
  readonly parse: number;
  /** Requests per client IP per 5 minutes on the spec-entry paths. */
  readonly spec: number;
}

/**
 * The CloudFront web ACL, created once per rule set. Its name carries a hash of the
 * rules, so a rule change creates a new ACL and never updates one in place; the old
 * ACL is deleted with the lock value of its create response after the distribution
 * has moved to the new one.
 */
export class EdgeWebAcl extends Construct {
  readonly arn: string;
  /** The distribution depends on it, so the ACL is deleted after the distribution. */
  readonly deleter: AwsCustomResource;

  constructor(scope: Construct, id: string, limits: RateLimits) {
    super(scope, id);
    const acl = edgeAclDefinition(limits);
    const account = Stack.of(this).account;
    const policy = AwsCustomResourcePolicy.fromSdkCalls({
      resources: [`arn:aws:wafv2:${EDGE_REGION}:${account}:global/*`],
    });
    const create = {
      service: "WAFV2",
      action: "CreateWebACL",
      region: EDGE_REGION,
      parameters: acl,
      physicalResourceId: PhysicalResourceId.fromResponse("Summary.Id"),
    };
    const creator = new AwsCustomResource(this, "Create", {
      onCreate: create,
      onUpdate: create,
      policy,
      installLatestAwsSdk: false,
    });
    const aclId = creator.getResponseField("Summary.Id");
    const ref = { Id: aclId, Name: acl.Name, Scope: SCOPE };
    const check = {
      service: "WAFV2",
      action: "GetWebACL",
      region: EDGE_REGION,
      parameters: ref,
      physicalResourceId: PhysicalResourceId.of(aclId),
      outputPaths: ["WebACL.Id"],
    };
    this.deleter = new AwsCustomResource(this, "Delete", {
      onCreate: check,
      onUpdate: check,
      onDelete: {
        service: "WAFV2",
        action: "DeleteWebACL",
        region: EDGE_REGION,
        parameters: { ...ref, LockToken: creator.getResponseField("Summary.LockToken") },
        ignoreErrorCodesMatching: "WAFNonexistentItemException",
      },
      policy,
      installLatestAwsSdk: false,
    });
    this.arn = creator.getResponseField("Summary.ARN");
  }
}

/** The CreateWebACL request (WAFv2 API shape) for the rate limits. */
export function edgeAclDefinition(limits: RateLimits) {
  const rules = [
    ...MANAGED_GROUPS.map((name, priority) => ({
      Name: name,
      Priority: priority,
      Statement: { ManagedRuleGroupStatement: { VendorName: "AWS", Name: name } },
      OverrideAction: { None: {} },
      VisibilityConfig: visibility(name),
    })),
    rateRule("rate-parse", MANAGED_GROUPS.length, limits.parse, {
      AndStatement: { Statements: [pathIs(PARSE_PATH), methodIs("POST")] },
    }),
    rateRule("rate-spec", MANAGED_GROUPS.length + 1, limits.spec, {
      OrStatement: { Statements: SPEC_PATHS.map(pathIs) },
    }),
  ];
  const request = {
    Scope: SCOPE,
    Description: "BORAMAE edge rules: AWS managed groups and per-client rate limits",
    DefaultAction: { Allow: {} },
    Rules: rules,
    VisibilityConfig: visibility("boramae-edge"),
  };
  // The hash covers the whole request: a change to any field must give a new name,
  // because CreateWebACL fails on a name that exists.
  const hash = createHash("sha256").update(JSON.stringify(request)).digest("hex");
  return { Name: NAME_PREFIX + hash.slice(0, 12), ...request };
}

function rateRule(name: string, priority: number, limit: number, scopeDown: object) {
  return {
    Name: name,
    Priority: priority,
    Statement: {
      RateBasedStatement: {
        Limit: limit,
        EvaluationWindowSec: RATE_WINDOW_S,
        AggregateKeyType: "IP",
        ScopeDownStatement: scopeDown,
      },
    },
    Action: { Block: { CustomResponse: { ResponseCode: TOO_MANY_REQUESTS } } },
    VisibilityConfig: visibility(name),
  };
}

function pathIs(path: string) {
  return byteMatch({ UriPath: {} }, path);
}

function methodIs(method: string) {
  return byteMatch({ Method: {} }, method);
}

function byteMatch(field: object, value: string) {
  return {
    ByteMatchStatement: {
      SearchString: value,
      FieldToMatch: field,
      PositionalConstraint: "EXACTLY",
      TextTransformations: [{ Priority: 0, Type: "NONE" }],
    },
  };
}

function visibility(metricName: string) {
  return {
    SampledRequestsEnabled: true,
    CloudWatchMetricsEnabled: true,
    MetricName: metricName,
  };
}
