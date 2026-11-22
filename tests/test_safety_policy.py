from src.tools.safety_policy import classify_command


def test_read_only_diagnostic_allowed():
    assert classify_command("kubectl get pods -n production").status == "ALLOW_READ_ONLY"


def test_destructive_commands_require_approval():
    for command in ("kubectl delete pod checkout", "DROP TABLE events", "terraform apply"):
        assert classify_command(command).status == "REQUIRES_HUMAN_APPROVAL"


def test_shell_chaining_requires_approval():
    assert classify_command("kubectl get pods; kubectl delete pod x").status == "REQUIRES_HUMAN_APPROVAL"
