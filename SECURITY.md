# Security policy

## Supported versions

ModelDiff is in early development. Security fixes are made on the `main` branch and included in the next release.

## Reporting a vulnerability

Please do **not** open a public issue for security problems.

Use GitHub's private vulnerability reporting: open the repository's **Security** tab and choose **Report a vulnerability**. Include:

- what the problem is and where it is (file, command, or input format);
- steps to reproduce, ideally with a minimal suite, config, or result file;
- the impact you expect.

You should receive an acknowledgement within a week. We will keep you informed of the fix and credit you in the release notes if you wish.

## Scope notes

- Suite, config, and recorded-output files are trusted input: they are YAML/JSON parsed with `yaml.safe_load` and `json.loads`.
- `--plugin` **executes Python code** from the given file or module. Only load plugins you trust.
- Result files may contain model outputs. See "Result files and privacy" in the README for the `capture_output` setting.
