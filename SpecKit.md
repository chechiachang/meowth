### Speckit

https://github.com/github/spec-kit

### Initialize speckit project

```
uvx --from git+https://github.com/github/spec-kit.git specify init meowth2
```

### principles

```
/speckit.constitution Create principles focused on code quality, testing standards, and environment safety
```

### Feature: specifications, plan, implementation

Create feature branch and generate ./specs/*

```
/speckit.specify Build an application that can interact with notion.so api and slack api. The application should be able to watch slack channels for specific slack app commands and create corresponding pages in a designated Notion database. The application should be able to aggregate slack messages based on certain keywords and create summary reports in Notion on a scheduled basis. The app should able to summarize slack messages in thread and history. The application should also support organizaing duplicate messages into a single Notion page with references to the original messages in Slack. Ensure the application handles authentication, error handling, and rate limiting for both APIs.
```
Review specs. To clarify specs

```
/speckit.clarify
```

techincal implementation
- Use python
- Official slack-python-sdk
- Good community support notion-sdk-py

```
/speckit.plan The application use python. The application uses uv as the package manager and project manager. Put source code in ./src. The application will use the official slack-python-sdk to interact with the Slack API and notion-sdk-py to interact with the Notion API. The application will be structured in a modular way to separate concerns such as API interactions, data processing, and scheduling. The application will implement authentication mechanisms for both APIs, handle errors gracefully, and respect rate limits imposed by the APIs. The application will also include unit tests to ensure code quality and reliability. Put tests in ./tests.
```

Generate tasks for implementation

```
/speckit.tasks
```

---

## Notes

### How-to generate spec

- Start from Speckit examples
- Manually write speckit.constitution, speckit.specify, speckit.plan
- Use copilot to generate from existing repository

```
# vscode
# open atlas

anylize the repo, generate following promp with details: speckit.constitution, speckit.specify, speckit.plan
```
