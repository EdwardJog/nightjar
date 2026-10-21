"""Two actual Streamlit sessions exercise the hosted entry point independently."""
from pathlib import Path
from app.tests.test_interface import JourneyAppTest, button, field


def test_cloud_visitors_demo_delete_and_refresh_are_isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("NIGHTJAR_STORAGE_MODE", "session")
    monkeypatch.setenv("NIGHTJAR_DATA_DIR", str(tmp_path / "must_not_exist"))
    entry = str(Path(__file__).resolve().parents[1] / "cloud_entry.py")
    alice = JourneyAppTest(entry, default_timeout=60).run()
    button(alice, "Create my space").click().run()
    field(alice.text_input, "What should we call you? (optional)").set_value("Alice")
    button(alice, "Continue").click().run()
    button(alice, "Create my space").click().run()
    assert alice.session_state["workspace"]["profile"]["name"] == "Alice"
    bob = JourneyAppTest(entry, default_timeout=60).run()
    assert bob.session_state["workspace"] is None
    button(bob, "Create my space").click().run()
    field(bob.text_input, "What should we call you? (optional)").set_value("Bob")
    button(bob, "Continue").click().run()
    button(bob, "Create my space").click().run()
    alice.run()
    assert alice.session_state["workspace"]["profile"]["name"] == "Alice"
    assert bob.session_state["workspace"]["profile"]["name"] == "Bob"
    button(alice, "Settings").click().run()
    field(alice.checkbox, "Delete all profiles, recordings, experiments and decisions").check()
    button(alice, "Delete all session spaces").click().run()
    assert alice.session_state["workspace"] is None
    bob.run()
    assert bob.session_state["workspace"]["profile"]["name"] == "Bob"
    fresh = JourneyAppTest(entry, default_timeout=60).run()
    assert fresh.session_state["workspace"] is None
    button(fresh, "Explore the demo").click().run()
    assert fresh.session_state["workspace"] is None
    assert not any(a.exception for a in (alice, bob, fresh))
    assert not (tmp_path / "must_not_exist").exists()
