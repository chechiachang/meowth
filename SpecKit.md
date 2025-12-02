### Speckit

https://github.com/github/spec-kit

### Initialize speckit project

```
uvx --from git+https://github.com/github/spec-kit.git specify init meowth
```

```
# principles
/speckit.constitution Create principles focused on code quality, test-driven development.
```

### Spec 1: slack app

Slack bolt

```
/speckit.specify Build an python slack app named meowth that can interact with slack api. The application should be able to watch app_mention in slack channels. When app_mention, it respond "Meowth, that's right!".

/speckit.clarify

/speckit.plan The application use python. The application uses uv as the package manager and project manager, run all python and test through uv run. Put source code in ./src/meowth. The application will use the official slack bolt-python to interact with the Slack API. The app auth with bot token and app token. The application will also include unit tests to ensure code quality and reliability. Put tests in ./tests.

/speckit.tasks
```

OpenAI

```
/speckit.specify Add OpenAI integration to the slack app meowth. When app_mention in a slack threads, the app use OpenAI to chat completion to generate a response and respond in threads. Use llama index agent to handle the chat completion.

/speckit.clarify
/speckit.plan
/speckit.tasks
```

Summerize

```
/speckit.specify Implement tools for ai agent to use. When app_mention, the app ai choose tools to respond. For example, if user ask ai to summerize messages, the app use slack api to fetch thread messages in the channel, summerize the messages using OpenAI, and respond in threads.
/speckit.clarify
/speckit.plan 
```
