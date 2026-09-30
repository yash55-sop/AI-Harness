# Security boundaries

Enabling Shell gives a model permission to execute commands with the Python process's
permissions and environment. CodingAgent and the CLI enable Shell by default.
`enable_shell=False`, `--no-shell`, or `--read-only` can reduce enabled capabilities.
No approval callback or command allowlist is implemented in v0.1.

Filesystem tools resolve paths and check containment within an existing workspace.
Relative traversal and absolute paths outside that workspace are rejected. Resolving
also prevents following static symlinks/junctions outside it. NTFS alternate streams
are rejected. WriteFile does not overwrite hard-linked files. Reads of existing hard
links remain reads of files present in the workspace; avoid constructing workspaces
with aliases to sensitive files.

These checks assume a trusted filesystem. Concurrent path replacement can race a
check and access. Workspace checks do not impose OS containment, and shell commands
can access any resource allowed to the host process. Use a disposable workspace and
an isolated container/VM for untrusted repositories or stronger guarantees.

Shell uses `shell=False`, stdin from DEVNULL, a resolved cwd, an execution timeout,
and bounded byte buffers while draining stdout/stderr. Nonzero exit codes and timeouts
are returned as structured observations. The timeout kills the direct process and
attempts to kill its process tree/group. Detached processes or descendants after a
parent exit may escape that cleanup. Network, CPU, disk writes, and subprocess memory
are not restricted. File writes replace the target directly and are not transactional.

ReadFile limits bytes and only reads regular UTF-8 files. ListFiles limits entry count.
Agent caps output appended to model context. These limits do not cap the memory used
inside arbitrary custom tools before they return a result.

Configuration secrets are masked and excluded from dumps. Built-in logs contain only
event metadata, not prompts, arguments, outputs, raw HTTP bodies, or credentials.
Conversation history and run metadata can include sensitive values. File contents
and command outputs are sent to the configured provider; exclude secrets from the
workspace and avoid commands that print them. Shell inherits credentials in the
process environment. Custom tools must enforce their own boundaries and logging policy.

Failed runs roll back conversation context only. Already executed tools may have
changed the workspace. Review changes and use version control/backups as appropriate.
