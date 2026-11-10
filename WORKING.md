# How we work

This file is for everyone on the team and for every Claude agent that joins us. Agents read it in full before they post or push anything.

## Where things live

- **Discord, channel #general:** talking. Humans and agents, always in English.
- **GitHub issues in this repo:** tasks, one issue per task.
- **This repo:** code, on branches as described below.

## Repo layout

- `README.md`, `WORKING.md` (this file), `SETUP.md` (connecting your agent to Discord) and `LICENSE` stay at the top.
- `docs/` holds event material and our own notes. The official rules are in `docs/participant-guidebook.pdf` on pages 22 and 23.
- `src/` holds the project code and starts empty. Nothing goes in there before hacking starts on Friday 13 November at 19:30.

Once we have picked a stack we add its layout here.

## Branches and merging

- Every person works on their own branch named `name/topic`, for example `alex/login-form`.
- When a piece works, open a pull request into `main` and write in it what you tested and how.
- Only one person merges into `main`. We decide who at the kickoff on Friday and nobody else pushes there.
- Pull `main` into your branch often, because ten small merges hurt less than one big merge at four in the morning.

## Tasks

- Every task is an issue. Assign yourself before you start so nobody builds the same thing twice.
- Close the issue from the pull request with `Closes #12`.
- No task lists in shared files. When two people edit the same file it ends in merge conflicts (we tried it on purpose before the event).

## Agents in Discord

- Every status message starts with `RUNNING:`, `DONE:`, `QUESTION:` or `BLOCKED:` followed by the issue or branch. Example: `DONE: #12 on alex/login-form, npm test passes (14 tests)`.
- `DONE` only after a test, with the command you ran and its result.
- Keep messages short. Logs, diffs and long output go into the issue and Discord gets the link.
- Agents talk to each other directly by mentioning `@its-name`. This only works with the one line change from [SETUP.md](SETUP.md), step 3.
- An agent takes tasks from its own human. Questions from anyone else it answers.
- Answer another agent only when it asked you something or handed you a task. No thanks, no "got it", no small talk between agents.
- After three messages back and forth between two agents without a result, stop and ask a human.
- Ask a human before anything that is hard to undo: force pushes, deleting branches, changing repo settings or posting outside our server.

## Never

- Credentials, tokens, API keys or the contents of a `.env` file in the repo, in issues or in Discord. If one leaks anyway, tell its owner straight away so they can replace it.
- Project code before hacking starts on Friday 13 November at 19:30. The guidebook disqualifies code written in advance for the idea, while open source libraries are allowed.

## Deadlines (Finnish time)

- **Fri 13 Nov, 23:59:** draft submission with our challenge. One of us creates the project on the platform.
- **Sun 15 Nov, 10:00:** final submission. The project goes from DRAFT to FINAL and the form closes after that.
- **Sun 15 Nov, 10:30 to 14:00:** peer review on site. All of us have to be there or we cannot win a main prize.

The submission needs a name, a punchline, a description, the challenge, the tech we used, a public pitch video of at most two minutes on YouTube or Vimeo, demo and code links, the pitch deck as a PDF plus the phone numbers and Discord names of everyone in the team. The organisers must be able to reach the code and everything is submitted under the MIT licence (see LICENSE).

## New agents

When a new bot joins our Discord server, GLaDOS points it to this file. Read it, then say hello in #general with the name of your human and what you are working on.
