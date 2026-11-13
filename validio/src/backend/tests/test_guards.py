"""Each guard must fail on a planted example and pass on a clean tree."""

import subprocess
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"


def run(script: str, root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(SCRIPTS / script), str(root)],
                          check=False, capture_output=True, text=True)


def clean_tree(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "ok.py").write_text('BASE = "https://junction26.valioaimo.fi"\n')
    return tmp_path


def test_secret_check_catches_key(tmp_path):
    root = clean_tree(tmp_path)
    assert run("check_no_secrets.sh", root).returncode == 0
    (root / "src" / "leak.py").write_text('KEY = "junct_' + "a1B2" * 10 + '"\n')
    r = run("check_no_secrets.sh", root)
    assert r.returncode == 1
    assert "leak.py" in r.stdout
    assert "a1B2a1B2" not in r.stdout  # never print the secret itself


def test_secret_check_catches_private_key(tmp_path):
    root = clean_tree(tmp_path)
    (root / "k.pem").write_text("-----BEGIN EC " + "PRIVATE KEY-----\nabc\n")
    assert run("check_no_secrets.sh", root).returncode == 1


def test_forbidden_hosts_check(tmp_path):
    root = clean_tree(tmp_path)
    assert run("check_forbidden_hosts.sh", root).returncode == 0
    for host in ("toimitustukku.valioaimo.fi", "api.valioaimo.fi"):
        bad = root / "src" / "bad.py"
        bad.write_text(f'URL = "https://{host}/cart"\n')
        r = run("check_forbidden_hosts.sh", root)
        assert r.returncode == 1, host
        assert "bad.py" in r.stdout
        bad.unlink()
    # docs may name the hosts to explain the rule
    (root / "docs").mkdir()
    (root / "docs" / "rules.md").write_text("never call api.valioaimo.fi\n")
    assert run("check_forbidden_hosts.sh", root).returncode == 0


def test_guards_pass_on_this_repo():
    root = SCRIPTS.parent
    assert run("check_no_secrets.sh", root).returncode == 0
    assert run("check_forbidden_hosts.sh", root).returncode == 0


def test_secret_check_catches_nvidia_and_modal_tokens(tmp_path):
    for i, leak in enumerate(['NVIDIA_API_KEY="nvapi-' + "Ab1_" * 8 + '"',
                              'MODAL_TOKEN_SECRET="as-' + "Ab12" * 6 + '"',
                              'MODAL_TOKEN_ID="ak-' + "Ab12" * 6 + '"']):
        (tmp_path / str(i)).mkdir()
        root = clean_tree(tmp_path / str(i))
        assert run("check_no_secrets.sh", root).returncode == 0
        (root / "src" / "leak.py").write_text(leak + "\n")
        r = run("check_no_secrets.sh", root)
        assert r.returncode == 1, leak
        assert "Ab12Ab12" not in r.stdout and "Ab1_Ab1_" not in r.stdout
