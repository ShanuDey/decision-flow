---
title: "Agent guide"
---

Let your AI agent install the Decision Flow MCP server for you. Once connected, the server tells the agent how to use its tools. For the tool list and key handling, see [Connect an AI agent](mcp).

## Install with an agent

1. Open **Settings → API keys** and choose **Connect an AI agent**.
2. Name the agent, pick its scopes and expiry, and choose **Create key and show setup**.
3. Copy **Ask your agent to install it** and paste it into your agent. The server URL and the key are already filled in. The key is shown once, so copy the prompt before closing the dialog.
4. Check the connection: "List my decision flows."

## Try it

Once connected, start with a short request and let the agent fill in the details:

````markdown
Create a credit application flow and test it with a sample applicant.
````

For more control, spell out the inputs, rules and outputs:

````markdown
Build a loan eligibility flow called "Loan check".
Inputs: income (number) and credit_score (number).
Approve when income is at least 30000 and credit_score is at least 600, otherwise decline.
The flow should output a text field named decision, set to "approved" or "declined".
Validate it, save it as a draft, then run the draft with income 45000 and credit_score 650.
Tell me the result and which branch it took, using the run's steps.
````

The agent should create the flow, run it, and answer `approved` with the Condition step as the reason. Open the flow in the editor to see the graph it built, and the run's [trace](traces) to see the same steps. Then ask it to change something, such as "decline anyone under 21 using a new age input", and run it again.
