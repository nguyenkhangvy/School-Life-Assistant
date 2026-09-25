from sla_agent import credentials
from sla_agent.state import State, agent_home, load_state, save_state


def test_edusoft_password_goes_to_the_keyring_under_the_student_id(isolated_agent):
    credentials.save_edusoft("ITITIU20001", "s3cret-pass")

    assert isolated_agent.entries == {("SchoolLifeAssistant-EduSoft", "ITITIU20001"): "s3cret-pass"}
    assert credentials.load_edusoft("ITITIU20001") == "s3cret-pass"


def test_device_key_goes_to_the_keyring_under_the_server_address(isolated_agent):
    credentials.save_device_key("https://sla.example.com", "sla_key-123")

    assert credentials.load_device_key("https://sla.example.com") == "sla_key-123"
    assert ("SchoolLifeAssistant-DeviceKey", "https://sla.example.com") in isolated_agent.entries


def test_forget_removes_both_secrets_even_if_one_is_missing(isolated_agent):
    credentials.save_edusoft("ITITIU20001", "s3cret-pass")

    credentials.forget("ITITIU20001", "https://sla.example.com")

    assert isolated_agent.entries == {}


def test_state_file_round_trip_never_contains_secrets(isolated_agent):
    credentials.save_edusoft("ITITIU20001", "s3cret-pass")
    state = State(server_url="https://sla.example.com", student_id="ITITIU20001", paused="bad_credentials")

    save_state(state)

    assert load_state() == state
    assert "s3cret-pass" not in (agent_home() / "state.json").read_text(encoding="utf-8")


def test_missing_state_file_gives_an_empty_state():
    assert load_state() == State()
