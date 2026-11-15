import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

import { App } from "aws-cdk-lib";
import { Match, Template } from "aws-cdk-lib/assertions";
import { describe, expect, it } from "vitest";

import { edgeAclDefinition } from "../lib/edge-acl.ts";
import { BoramaeStack } from "../lib/stack.ts";

const ENV = { account: "177950257164", region: "us-west-2" };
const EM_DASH = "—";
const EMAIL_PATTERN = /[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9.-]+/;

function synth(context: Record<string, string> = {}): Template {
  const app = new App({ context });
  return Template.fromStack(new BoramaeStack(app, "Boramae", { env: ENV }));
}

const template = synth();
const json = template.toJSON();
const parameters = json.Parameters;

interface WafRule {
  Statement: { RateBasedStatement?: object; ManagedRuleGroupStatement?: { Name: string } };
  Action?: { Block?: { CustomResponse?: { ResponseCode: number } } };
}

function edgeAclRules(t: Template): WafRule[] {
  const [creator] = Object.values(
    t.findResources("Custom::AWS", { Properties: { Create: Match.stringLikeRegexp("CreateWebACL") } }),
  );
  return JSON.parse(creator.Properties.Create).parameters.Rules;
}

function rateRuleCodes(t: Template): number[] {
  return edgeAclRules(t)
    .filter((rule) => rule.Statement.RateBasedStatement !== undefined)
    .map((rule) => rule.Action?.Block?.CustomResponse?.ResponseCode ?? 0);
}

/** Container variables that api/boramae/config.py would refuse at start-up. */
function unknownSettings(t: Template): string[] {
  const config = readFileSync(new URL("../../api/boramae/config.py", import.meta.url), "utf8");
  const known = [...config.matchAll(/^ {4}(\w+): .+ = /gm)].map(([, field]) => `BORAMAE_${field.toUpperCase()}`);
  const [task] = Object.values(t.findResources("AWS::ECS::TaskDefinition"));
  const names: string[] = task.Properties.ContainerDefinitions[0].Environment.map(
    (entry: { Name: string }) => entry.Name,
  );
  return names.filter((name) => !known.includes(name));
}

function managedGroupNames(t: Template): string[] {
  return edgeAclRules(t).flatMap((rule) => rule.Statement.ManagedRuleGroupStatement?.Name ?? []);
}

function rewrite(uri: string): string {
  const code = readFileSync(new URL("../lib/index-rewrite.js", import.meta.url), "utf8");
  const handler = new Function(`${code}\nreturn handler;`)();
  return handler({ request: { uri } }).uri;
}

describe("BoramaeStack", () => {
  it("should block all public access on both buckets", () => {
    template.resourcePropertiesCountIs(
      "AWS::S3::Bucket",
      {
        PublicAccessBlockConfiguration: {
          BlockPublicAcls: true,
          BlockPublicPolicy: true,
          IgnorePublicAcls: true,
          RestrictPublicBuckets: true,
        },
      },
      2,
    );
  });

  it("should answer 429 from both rate rules of the CloudFront web ACL", () => {
    expect(rateRuleCodes(template)).toEqual([429, 429]);
  });

  it("should associate the regional web ACL with the API load balancer", () => {
    template.hasResourceProperties("AWS::WAFv2::WebACLAssociation", {
      ResourceArn: {
        "Fn::GetAtt": [Match.anyValue(), "ECSManagedResourceArns.IngressPath.LoadBalancerArn"],
      },
    });
  });

  it("should block API requests whose origin header is not the CloudFront value", () => {
    template.hasResourceProperties("AWS::WAFv2::WebACL", {
      Scope: "REGIONAL",
      Rules: [
        Match.objectLike({
          Action: { Block: {} },
          Statement: {
            NotStatement: {
              Statement: {
                ByteMatchStatement: Match.objectLike({
                  FieldToMatch: { SingleHeader: { Name: "x-boramae-origin" } },
                  SearchString: { "Fn::Join": ["", Match.arrayWith(["{{resolve:secretsmanager:"])] },
                }),
              },
            },
          },
        }),
      ],
    });
  });

  it.each(["BudgetAmountUsd", "BudgetAlertAddress"])(
    "should give the budget parameter %s no default",
    (name) => {
      expect(parameters[name]).not.toHaveProperty("Default");
    },
  );

  it("should mark the budget alert address NoEcho", () => {
    expect(parameters.BudgetAlertAddress.NoEcho).toBe(true);
  });

  it("should hold no em dash in any name or description", () => {
    expect(JSON.stringify(json)).not.toContain(EM_DASH);
  });

  it("should hold no e-mail address", () => {
    expect(JSON.stringify(json)).not.toMatch(EMAIL_PATTERN);
  });

  it("should send the origin header value only as a Secrets Manager dynamic reference", () => {
    template.hasResourceProperties("AWS::CloudFront::Distribution", {
      DistributionConfig: {
        Origins: Match.arrayWith([
          Match.objectLike({
            OriginCustomHeaders: [
              {
                HeaderName: "x-boramae-origin",
                HeaderValue: {
                  "Fn::Join": ["", Match.arrayWith(["{{resolve:secretsmanager:"])],
                },
              },
            ],
          }),
        ]),
      },
    });
  });

  it("should run the API task on ARM64", () => {
    template.hasResourceProperties("AWS::ECS::TaskDefinition", {
      RuntimePlatform: { CpuArchitecture: "ARM64", OperatingSystemFamily: "LINUX" },
    });
  });

  it("should cap the service at one task without the CloudFront web ACL", () => {
    synth({ edgeWaf: "off" }).hasResourceProperties("AWS::ECS::ExpressGatewayService", {
      ScalingTarget: Match.objectLike({ MaxTaskCount: 1 }),
    });
  });

  it("should create no CloudFront web ACL when edgeWaf is off", () => {
    synth({ edgeWaf: "off" }).resourceCountIs("Custom::AWS", 0);
  });

  it("should attach no web ACL to the distribution when edgeWaf is off", () => {
    synth({ edgeWaf: "off" }).hasResourceProperties("AWS::CloudFront::Distribution", {
      DistributionConfig: Match.objectLike({ WebACLId: Match.absent() }),
    });
  });

  it("should hold the three AWS managed rule groups in the CloudFront web ACL", () => {
    expect(managedGroupNames(template)).toEqual([
      "AWSManagedRulesAmazonIpReputationList",
      "AWSManagedRulesCommonRuleSet",
      "AWSManagedRulesKnownBadInputsRuleSet",
    ]);
  });

  it("should run the API task on X86_64 when arch is x86_64", () => {
    synth({ arch: "x86_64" }).hasResourceProperties("AWS::ECS::TaskDefinition", {
      RuntimePlatform: Match.objectLike({ CpuArchitecture: "X86_64" }),
    });
  });

  it.each<Record<string, string>>([
    { rateLimitParse: "abc" },
    { rateLimitSpec: "9" },
    { arch: "arm" },
    { edgeWaf: "of" },
  ])("should refuse the context %o at synth", (context) => {
    expect(() => synth(context)).toThrow(/^context /);
  });

  it("should name the CloudFront web ACL after a hash of its whole request", () => {
    const { Name, ...request } = edgeAclDefinition({ parse: 100, spec: 300 });
    const hash = createHash("sha256").update(JSON.stringify(request)).digest("hex");
    expect(Name).toBe(`boramae-edge-${hash.slice(0, 12)}`);
  });

  it("should set only container variables that the API settings know", () => {
    expect(unknownSettings(template)).toEqual([]);
  });
});

describe("index rewrite function", () => {
  it.each([
    ["/", "/index.html"],
    ["/ko/", "/ko/index.html"],
    ["/en/methods", "/en/methods/index.html"],
    ["/demo/manifest.json", "/demo/manifest.json"],
    ["/ko/__next.$d$locale.txt", "/ko/__next.$d$locale.txt"],
    ["/ko/__next.$d$locale.__PAGE__.txt", "/ko/__next.$d$locale/__PAGE__.txt"],
    ["/en/methods/__next.$d$locale.methods.__PAGE__.txt", "/en/methods/__next.$d$locale/methods/__PAGE__.txt"],
  ])("should map %s to %s", (uri, expected) => {
    expect(rewrite(uri)).toBe(expected);
  });
});
