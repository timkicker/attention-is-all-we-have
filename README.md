# Attention Is All We Have

A kitchen's purchasing agent orders from Valio Aimo through **Validio**. Within the Rules the kitchen sets, the agent orders alone. Above them it needs the owner's approval, and beyond them it is blocked.

Validio is our entry for Valio Aimo's challenge "Trusted Trade Agents" at Junction 2026. Any MCP client can connect to it as the kitchen's agent. Cedar rules that the model cannot override make each decision, from Valio's own data and the kitchen's signed Spend Pass. Each step goes into one hash-chained ledger with a signed head.

- Live: https://timkicker--validio.us-east.modal.run (click **Try the demo kitchen**, approval code 246810)

Start in [validio/README.md](validio/README.md) for the quick start with an MCP client, the pages, the rules, the architecture and how to run, test and deploy it. The plan and the reasoning behind each part are in [PROJECT_BLUEPRINT-validio.md](PROJECT_BLUEPRINT-validio.md).

Our second project is for MariaDB's challenge "Wikipedia Through Time". **Parallax** lines up how different language editions of Wikipedia tell the same event, claim by claim and through time, with MariaDB's system-versioned tables and vector search in one query. It only shows evidence and never edits Wikipedia. Everything for it lives in [parallax/](parallax/README.md): the product in [docs/PRODUCT.md](parallax/docs/PRODUCT.md), the research in [docs/RESEARCH.md](parallax/docs/RESEARCH.md) and the build plan in [PLAN.md](parallax/PLAN.md).
