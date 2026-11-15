import { App } from "aws-cdk-lib";

import { BoramaeStack } from "../lib/stack.ts";

const app = new App();
// The BORAMAE member account only, never the management account (TODOS.md, D-12).
new BoramaeStack(app, "Boramae", {
  env: { account: "177950257164", region: "us-west-2" },
  description: "BORAMAE app, API and edge",
});
