# Step 1: Read the JSON that the harness sends via stdin
data = json.load(sys.stdin)

# Step 2: Extract the bash command the model wants to run
command = data.get("tool_input", {}).get("command", "")

# Step 3: Define what we want to protect
protected_files = ["expense-tracker.db", ".env", "migrations/"]

# Step 4: Define what counts as dangerous
dangerous_commands = ["rm", "rm -", "unlink", ">", "truncate"]

# Step 5: Check if the command is dangerous AND targets a protected file
for dangerous in dangerous_commands:
    if dangerous in command:
        for protected in protected_files:
            if protected in command:
                # Block it: exit 2 + error message on stderr
                print(
                    f"BLOCKED: cannot run '{command}' — "
                    f"'{protected}' is a protected file",
                    file=sys.stderr
                )
                sys.exit(2)

# Step 6: If we get here, the command is fine — exit 0
sys.exit(0)