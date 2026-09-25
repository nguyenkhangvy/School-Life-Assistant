import keyring
import pytest
from keyring.backend import KeyringBackend
from keyring.errors import PasswordDeleteError


class MemoryKeyring(KeyringBackend):
    """Stands in for Windows Credential Manager during tests."""

    priority = 1

    def __init__(self):
        super().__init__()
        self.entries = {}

    def set_password(self, service, username, password):
        self.entries[(service, username)] = password

    def get_password(self, service, username):
        return self.entries.get((service, username))

    def delete_password(self, service, username):
        if (service, username) not in self.entries:
            raise PasswordDeleteError("not found")
        del self.entries[(service, username)]


@pytest.fixture(autouse=True)
def isolated_agent(tmp_path, monkeypatch):
    """Every agent test gets a fake keyring and its own agent folder:
    tests never touch the real Credential Manager or %LOCALAPPDATA%."""
    fake = MemoryKeyring()
    previous = keyring.get_keyring()
    keyring.set_keyring(fake)
    monkeypatch.setenv("SLA_AGENT_HOME", str(tmp_path / "agent-home"))
    yield fake
    keyring.set_keyring(previous)
