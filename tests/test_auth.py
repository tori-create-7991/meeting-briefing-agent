import os
import stat

from meeting_briefing_agent.auth import _save_token


class FakeCreds:
    def to_json(self):
        return '{"token": "fake"}'


def test_save_token_sets_0600_on_new_file(tmp_path):
    token_path = tmp_path / "token.json"

    _save_token(FakeCreds(), str(token_path))

    mode = stat.S_IMODE(os.stat(token_path).st_mode)
    assert mode == 0o600


def test_save_token_tightens_permissions_on_pre_existing_file(tmp_path):
    token_path = tmp_path / "token.json"
    token_path.write_text('{"token": "stale"}')
    os.chmod(token_path, 0o644)

    _save_token(FakeCreds(), str(token_path))

    mode = stat.S_IMODE(os.stat(token_path).st_mode)
    assert mode == 0o600
