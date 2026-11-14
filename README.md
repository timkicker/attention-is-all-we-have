# Attention Is All We Have

*Your agent places the order. Validio checks it before any money moves.*

Validio is our entry for Valio Aimo's challenge "Trusted Trade Agents" at Junction 2026. It sits between a kitchen's purchasing agent and Valio's wholesale API. For every fact it uses (stock, price, allergen, claim) it knows how far that fact can be trusted. Rules the AI model cannot override decide whether the agent may order alone, has to ask a person or is blocked. Every step lands in one hash-chained log that the kitchen and Valio read the same way.

![Sketch of the three screens: the agent's calls, the kitchen's web app and the approval on the phone](docs/img/screens.png)

This sketch is from the plan. The web app on main has moved on since, the video shows it as it is now.

- Live demo: (link follows)
- Video: (link follows)
- Pitch deck: (link follows)

Start in [validio/README.md](validio/README.md). It explains the setup, the architecture and a quick look that needs no key and no data. The plan with the reasoning behind each part is [PROJECT_BLUEPRINT-validio.md](PROJECT_BLUEPRINT-validio.md).

Our second project, Zombie Facts for MariaDB's challenge "Wikipedia Through Time", lives in [zombie-facts/](zombie-facts/README.md). Its plan is [PROJECT_BLUEPRINT-zombie-facts.md](PROJECT_BLUEPRINT-zombie-facts.md).
