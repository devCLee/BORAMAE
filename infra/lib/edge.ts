import { fileURLToPath } from "node:url";

import { Duration, aws_cloudfront as cloudfront, aws_s3 as s3, aws_wafv2 as wafv2 } from "aws-cdk-lib";
import * as origins from "aws-cdk-lib/aws-cloudfront-origins";
import { Construct } from "constructs";

import { EdgeWebAcl, type RateLimits } from "./edge-acl.ts";

/** The header that CloudFront adds on every request to the API origin. */
export const ORIGIN_HEADER = "x-boramae-origin";
const REWRITE_FILE = fileURLToPath(new URL("./index-rewrite.js", import.meta.url));
// The API answers within its 60 s request timeout (api/boramae/config.py); CloudFront
// allows up to 60 s without a quota increase.
const API_READ_TIMEOUT = Duration.seconds(60);

export interface EdgeProps {
  readonly webBucket: s3.IBucket;
  /** Folder under releases/ that the default behavior serves. */
  readonly releaseId: string;
  /** Host name of the API load balancer, with no scheme and no slash. */
  readonly apiDomain: string;
  readonly apiLoadBalancerArn: string;
  /** The origin header value, as a CloudFormation dynamic reference. */
  readonly originHeaderValue: string;
  /** Rate limits of the CloudFront web ACL; undefined means no CloudFront ACL. */
  readonly rateLimits?: RateLimits;
}

/** One CloudFront distribution in front of the web bucket and the API (DES-004). */
export class Edge extends Construct {
  readonly distribution: cloudfront.Distribution;
  readonly webAclArn?: string;

  constructor(scope: Construct, id: string, props: EdgeProps) {
    super(scope, id);
    const edgeAcl = props.rateLimits && new EdgeWebAcl(this, "WebAcl", props.rateLimits);
    this.webAclArn = edgeAcl?.arn;

    const apiOrigin = new origins.HttpOrigin(props.apiDomain, {
      protocolPolicy: cloudfront.OriginProtocolPolicy.HTTPS_ONLY,
      readTimeout: API_READ_TIMEOUT,
      customHeaders: { [ORIGIN_HEADER]: props.originHeaderValue },
    });
    // The Express load balancer routes by its own host name, so Host is not forwarded.
    const liveApi: cloudfront.BehaviorOptions = {
      origin: apiOrigin,
      viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
      allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
      cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
      originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
    };
    // ponytail: the API's Cache-Control sets the TTL (1 year on /r/, 300 s on /meta/);
    // a custom cache policy only if an origin response ever lacks that header.
    const storedApi: cloudfront.BehaviorOptions = {
      origin: apiOrigin,
      viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
      cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
    };
    const indexRewrite = new cloudfront.Function(this, "IndexRewrite", {
      code: cloudfront.FunctionCode.fromFile({ filePath: REWRITE_FILE }),
      runtime: cloudfront.FunctionRuntime.JS_2_0,
      comment: "Maps a folder path of the static export to its index.html",
    });

    this.distribution = new cloudfront.Distribution(this, "Distribution", {
      comment: "BORAMAE app and API",
      defaultRootObject: "index.html",
      // Edge locations in the US and in South Korea (CloudFront pricing page).
      priceClass: cloudfront.PriceClass.PRICE_CLASS_200,
      webAclId: this.webAclArn,
      defaultBehavior: {
        origin: origins.S3BucketOrigin.withOriginAccessControl(props.webBucket, {
          originPath: `/releases/${props.releaseId}`,
        }),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
        functionAssociations: [
          { function: indexRewrite, eventType: cloudfront.FunctionEventType.VIEWER_REQUEST },
        ],
      },
      additionalBehaviors: {
        "/api/*": liveApi,
        "/health": liveApi,
        "/r/*": storedApi,
        "/meta/*": storedApi,
      },
    });
    if (edgeAcl) {
      this.distribution.node.addDependency(edgeAcl.deleter);
    }

    this.addOriginGuard(props);
  }

  /** Regional web ACL on the load balancer: only requests from CloudFront pass. */
  private addOriginGuard(props: EdgeProps): void {
    const metric = (name: string) => ({
      cloudWatchMetricsEnabled: true,
      sampledRequestsEnabled: true,
      metricName: name,
    });
    const guard = new wafv2.CfnWebACL(this, "OriginGuard", {
      scope: "REGIONAL",
      description: "Blocks API requests that do not come through the BORAMAE distribution",
      defaultAction: { allow: {} },
      visibilityConfig: metric("boramae-origin-guard"),
      rules: [
        {
          name: "require-edge-header",
          priority: 0,
          action: { block: {} },
          visibilityConfig: metric("require-edge-header"),
          statement: {
            notStatement: {
              statement: {
                byteMatchStatement: {
                  fieldToMatch: { singleHeader: { Name: ORIGIN_HEADER } },
                  positionalConstraint: "EXACTLY",
                  searchString: props.originHeaderValue,
                  textTransformations: [{ priority: 0, type: "NONE" }],
                },
              },
            },
          },
        },
      ],
    });
    new wafv2.CfnWebACLAssociation(this, "OriginGuardAssociation", {
      resourceArn: props.apiLoadBalancerArn,
      webAclArn: guard.attrArn,
    });
  }
}
