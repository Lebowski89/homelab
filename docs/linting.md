## Linting

This repo makes use of both yaml and ansible linting.

See: *.yamllint and .ansible-lint files and the lint.yml workflow*

For common issues/warnings, such as:
+ Too-long Line length
+ Trailing spaces
+ Missing new line at end of documents
+ Missing docker_services_ prefix in role set_fact variables

I throw it at ChatGPT Codex and let it make a pull request with the linting changes (which I then review before merge)...

... or I just go in and manually fix it myself (and I try not have these issues in the first place).
