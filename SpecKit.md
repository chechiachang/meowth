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

```
/speckit.specify Build an python slack app named meowth that can interact with slack api. The application should be able to watch app_mention in slack channels. When app_mention, it respond "Meowth, that's right!".

/speckit.clarify

/speckit.plan The application use python. The application uses uv as the package manager and project manager, run all python and test through uv run. Put source code in ./src/meowth. The application will use the official slack bolt-python to interact with the Slack API. The app auth with bot token and app token. The application will also include unit tests to ensure code quality and reliability. Put tests in ./tests.
```


```
/speckit.specify The app should be able to watch app_mention in slack channels. When app_mention in a slack threads, the app summerize messages and respond summary in threads.

/speckit.clarify

/speckit.plan 
```
