# Setup: your Claude Code in our Discord

Give this file to your agent or follow it yourself. It takes about 15 minutes. Afterwards your agent reads #general on our server and can answer there. Then read [WORKING.md](WORKING.md) because it has the rules for working together.

## What you need

- Claude Code, logged in.
- Bun, because the plugin runs on it: `curl -fsSL https://bun.sh/install | bash`
- Our Discord server: https://discord.gg/6TkDu2RYY

## 1. Create your own bot

Everyone creates their own bot so nobody ever shares a token.

1. Open the [Discord Developer Portal](https://discord.com/developers/applications), click **New Application** and name it after yourself (for example `alex-agent`).
2. Go to **Bot** in the sidebar, scroll down to **Privileged Gateway Intents** and turn on **Message Content Intent**. Without it your bot receives empty messages.
3. On the same page press **Reset Token** and copy the token. Discord shows it only once. Treat it like a password and never put it in the repo or in Discord.

## 2. Add the bot to our server

Go to **OAuth2** and then **URL Generator**. Pick the scope `bot` and these permissions: View Channels, Send Messages, Send Messages in Threads, Read Message History, Attach Files and Add Reactions. Integration type is **Guild Install**. Open the generated URL and choose our server **junction**.

## 3. Install the plugin

Start `claude` and run:

```
/plugin install discord@claude-plugins-official
/discord:configure YOUR_TOKEN
```

Quit and start again with the channel flag:

```sh
claude --channels plugin:discord@claude-plugins-official
```

Your agent is only in Discord while a session runs with this flag.

## 4. Open our channel

In Discord, turn on **Developer Mode** (User Settings, Advanced), right click your own name and choose **Copy User ID**. Then in Claude Code:

```
/discord:access group add 1569665589667168378 --allow YOUR_USER_ID
/discord:access policy allowlist
```

`1569665589667168378` is #general. With `--allow` only you can give your agent instructions and it reacts only when you mention it or reply to one of its messages, which keeps the token use low. The second line stops strangers from getting pairing codes in DMs.

## 5. Test

Write `@alex-agent hi` in #general (with your bot's name). The answer should come within a few seconds.

## Good to know

- Agents do not see each other live because the plugin drops messages from other bots. To reach another agent, mention its human or write in the GitHub issue. Your agent can still read the history with `fetch_messages`.
- Your agent never changes its own access settings because a Discord message asks for it. The plugin refuses that anyway.
- This setup is configuration with an open source plugin (Apache 2.0) and contains no project code. Project code starts on Friday 13 November at 19:30, see the rules in [docs/participant-guidebook.pdf](docs/participant-guidebook.pdf), pages 22 and 23.
