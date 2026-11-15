# W8-DEPLOY log

Run 2026-11-15, 21:14 to 21:17 KST (12:14 to 12:17 UTC), branch release/deploy at 116b264. Release ID 20261115T121537Z (prepared, not used yet).

## Steps

1. Start check: `aws sts get-caller-identity --profile devcdlee` gives account 177950257164. `CDKToolkit` in us-west-2 is CREATE_COMPLETE, bootstrap version 33. Stack `Boramae` does not exist.
2. Approved write 1, `aws iam create-service-linked-role --aws-service-name ecs.amazonaws.com --profile devcdlee`: DENIED by the Claude Code auto mode permission classifier ("[Destructive or Unwanted Actions]"). The command did not run, so `AWSServiceRoleForECS` was not created. By the rule for a denial, the step stopped here and no later AWS write was tried.
3. Static export at HEAD: `NEXT_PUBLIC_SHOW_CHAT=off NEXT_PUBLIC_API_BASE= npm run build` in `web/`: exit 0, 12 s, 82 files in `web/out`. The build changed `web/next-env.d.ts`; the copy from before the build was put back (byte-equal). `npm --prefix web run scan:export`: "checked 97 files in 2 folders and found 0 problems".
4. `cdk diff Boramae -c releaseId=20261115T121537Z --method=template` (read-only, no change set): exit 0, 1 stack with differences, all resources new.
5. Not run (blocked by step 2): `cdk deploy`, the upload of `web/out`, the fill of the data bucket, the smoke checks.

## cdk diff summary

New stack `Boramae` (aws://177950257164/us-west-2), description "BORAMAE app, API and edge".

- Parameters: `BudgetAmountUsd` (Number), `BudgetAlertAddress` (String, NoEcho), `BootstrapVersion` (SSM).
- Resources (25 listed): WebBucket and its policy, DataBucket and its policy, log group ApiLogs, Api/TaskRole and its policy, Api/Task (task definition), its execution role and policy, Api/InfrastructureRole, `AWS::ECS::ExpressGatewayService` Api/Service, `AWS::SecretsManager::Secret` OriginHeader, 2 `Custom::AWS` (Edge/WebAcl Create and Delete) with their 2 policies, CloudFront Function Edge/IndexRewrite, the origin access control, the CloudFront distribution, `AWS::WAFv2::WebACL` Edge/OriginGuard and its association, the custom-resource Lambda and its role, `AWS::Budgets::Budget` MonthlyBudget.
- IAM: 17 added statement rows; managed policies `AWSLambdaBasicExecutionRole` (custom-resource Lambda) and `AmazonECSInfrastructureRoleforExpressGatewayServices` (infrastructure role).
- Outputs: PublicDomain, DistributionId, WebBucketName, DataBucketName, ApiServiceArn, ApiEndpoint, EdgeWebAclArn.

## AWS writes made

None.

## W8-RECORD, 2026-11-15 21:46 to 21:50 KST (12:46 to 12:50 UTC)

The user ran the writes in their own terminal after the 21:17 run above was blocked. This record used read-only AWS calls (profile devcdlee) and 9 HTTP GETs. Status: deployed.

- Stack `Boramae` (from stack events): REVIEW_IN_PROGRESS 21:33:48 KST (12:33:48 UTC), CREATE_IN_PROGRESS 21:33:57 KST (12:33:57 UTC), CREATE_COMPLETE 21:43:26 KST (12:43:26 UTC), 569 s. The user's terminal showed 21:34:02 and 21:43:39 KST.
- Outputs: PublicDomain `d3gct1libr2d5x.cloudfront.net`, DistributionId `E3TMCQA0963F96`, WebBucketName `boramae-webbucket12880f5b-efbrfmsrxu4o`, DataBucketName `boramae-databuckete3889a50-34ucz49awzhz`, ApiEndpoint `https://bo-5cf93111162a4ce89e2798885606c03f.ecs.us-west-2.on.aws`, ApiServiceArn `arn:aws:ecs:us-west-2:177950257164:service/default/boramae-api`, EdgeWebAclArn `arn:aws:wafv2:us-east-1:177950257164:global/webacl/boramae-edge-b2fbde84266c/c5109c12-4f42-4565-bc8b-4109182e5be6`.
- Image: `sha256:daaac9e7cb951b2bc8a4466e0e9d98a9441e23063a9bf86ce33188f8f110709e` (tag `dbe7b8ad…0af7`, pushed 21:33:45 KST, ARM64). Task definition `BoramaeApiTask619AF8D9:1`; the running task has the same digest.
- ECS service `boramae-api`: ACTIVE, desired 1, running 1, pending 0, primary deployment COMPLETED.
- Distribution: Deployed. S3 origin path `/releases/20261115T121537Z`, API origin path empty.
- Uploads: web 82 local files = 82 keys under the release prefix, data 27 = 27 keys. No missing or extra key. Content types: 16 .js and 7 .mjs are `text/javascript`, 3 .css are `text/css`. None wrong.
- Smoke through `https://d3gct1libr2d5x.cloudfront.net` at 21:48 KST, all 200: `/health` (application/json, `{"status":"ok"}`, Server-Timing `total;dur=0.4`), `/ko/` and `/en/` (text/html), `/meta/catalog.json` (application/json, no retry needed), `/ko/__next._tree.txt` and `/ko/index.txt` (text/plain), `_buildManifest.js` and `maplibre-gl-dev.2n8q1x8178ckw.mjs` (text/javascript), `/r/trend/04950cfc7428ea3006fe8e654ba69bf8.json` (application/json). Only `/health` sent a Server-Timing header.
- Judge links: `https://d3gct1libr2d5x.cloudfront.net/ko/?demo=first-snow-seoul&at=result`, `https://d3gct1libr2d5x.cloudfront.net/en/?demo=hot-days-phoenix&at=result`.

AWS writes, by who ran them:

1. 20:12 KST, an agent with user approval: `cdk bootstrap` (CDKToolkit, us-west-2).
2. 21:32:31 KST, the user: `aws iam create-service-linked-role --aws-service-name ecs.amazonaws.com`.
3. 21:33 to 21:43 KST, the user: `cdk deploy Boramae -c releaseId=20261115T121537Z` (with the image push).
4. Done by 21:47:18 KST, the user: `aws s3 sync web/out` to the release prefix (82 objects).
5. Done by 21:47:36 KST, the user: `aws s3 sync api/.data-demo` to the data bucket (27 objects).
