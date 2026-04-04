# Penny development recipes

repo_url := "git@github.com:HeinrichHartmann/Penny.git"

# Spawn an autonomous Claude Code agent to work on GitHub issues
# Usage: just spawn-agent 2 or just spawn-agent 8 9
spawn-agent +ticket_ids:
    #!/usr/bin/env bash
    set -euo pipefail

    ticket_ids="{{ticket_ids}}"
    dir_suffix=$(echo "$ticket_ids" | tr ' ' '-')
    target_dir="../Penny-ticket-${dir_suffix}"

    if [ -d "$target_dir" ]; then
        echo "Directory $target_dir already exists. Aborting."
        exit 1
    fi

    echo "Cloning repo to $target_dir..."
    git clone "{{repo_url}}" "$target_dir"

    # Build issue list
    issue_list=""
    gh_commands=""
    for id in $ticket_ids; do
        issue_list="${issue_list}- Issue #${id}"$'\n'
        gh_commands="${gh_commands}gh issue view ${id}"$'\n'
    done

    # Write CLAUDE.md
    {
        printf '%s\n' "# Agent Task" ""
        printf '%s\n' "You are an autonomous agent working on the Penny project." ""
        printf '%s\n' "## Assigned Issues" ""
        printf '%s' "$issue_list"
        printf '%s\n' "" "Read the issue details:"
        printf '%s\n' '```'
        printf '%s' "$gh_commands"
        printf '%s\n' '```' ""
        printf '%s\n' "## Your Mission" ""
        printf '%s\n' "1. Read and understand the assigned issues"
        printf '%s\n' "2. Read \`CONTEXT.md\` for architecture overview"
        printf '%s\n' "3. Read \`agents/WORKFLOW.md\` for detailed workflow guidelines"
        printf '%s\n' "4. Review relevant ADRs in \`ADR/\`"
        printf '%s\n' "5. Implement the changes with appropriate test coverage"
        printf '%s\n' "6. Run \`make test\` to verify"
        printf '%s\n' "7. Create a PR following the format in \`agents/WORKFLOW.md\`" ""
        printf '%s\n' "**Important**: Follow \`agents/WORKFLOW.md\` for PR format, including"
        printf '%s\n' "implementation notes about discoveries and any deviations from the issue."
    } > "$target_dir/CLAUDE.md"

    abs_target_dir="$(cd "$target_dir" && pwd)"
    window_name="penny-${dir_suffix}"

    echo "Creating tmux window '$window_name' and starting Claude Code..."
    tmux new-window -n "$window_name" -c "$abs_target_dir" "claude"
    echo "Agent spawned in tmux window '$window_name'"

# Spawn a Claude Code agent with custom instructions
# Usage: just spawn my-task "Refactor the database layer"
spawn name instructions:
    #!/usr/bin/env bash
    set -euo pipefail

    target_dir="../Penny-{{name}}"

    if [ -d "$target_dir" ]; then
        echo "Directory $target_dir already exists. Aborting."
        exit 1
    fi

    echo "Cloning repo to $target_dir..."
    git clone "{{repo_url}}" "$target_dir"

    {
        printf '%s\n' "# Agent Task" ""
        printf '%s\n' "You are an autonomous agent working on the Penny project." ""
        printf '%s\n' "## Your Task" ""
        printf '%s\n' "{{instructions}}" ""
        printf '%s\n' "## Guidelines" ""
        printf '%s\n' "1. Read \`CONTEXT.md\` for architecture overview"
        printf '%s\n' "2. Read \`agents/WORKFLOW.md\` for detailed workflow guidelines"
        printf '%s\n' "3. Review relevant ADRs in \`ADR/\`"
        printf '%s\n' "4. Implement the changes with appropriate test coverage"
        printf '%s\n' "5. Run \`make test\` to verify"
        printf '%s\n' "6. Create a PR following the format in \`agents/WORKFLOW.md\`" ""
        printf '%s\n' "**Important**: Follow \`agents/WORKFLOW.md\` for PR format, including"
        printf '%s\n' "implementation notes about discoveries and any deviations."
    } > "$target_dir/CLAUDE.md"

    abs_target_dir="$(cd "$target_dir" && pwd)"
    window_name="penny-{{name}}"

    echo "Creating tmux window '$window_name' and starting Claude Code..."
    tmux new-window -n "$window_name" -c "$abs_target_dir" "claude"
    echo "Agent spawned in tmux window '$window_name'"
