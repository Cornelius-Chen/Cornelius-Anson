from dugong_app.controller import DugongController
from dugong_app.core.events import DugongEvent


def test_controller_remote_signal_count_and_priority() -> None:
    controller = DugongController.__new__(DugongController)
    events = [
        DugongEvent(event_type="state_tick", event_id="e1", payload={"mode": "study"}),
        DugongEvent(event_type="mode_change", event_id="e2", payload={"mode": "rest"}),
    ]
    assert controller._signal_event_count(events) == 1
    picked = controller._pick_representative_remote_event(events)
    assert picked is not None
    assert picked.event_type == "mode_change"


def test_controller_auto_sync_policy_backoff() -> None:
    controller = DugongController.__new__(DugongController)
    controller._sync_idle_multiplier = 1
    controller._sync_idle_max_multiplier = 8

    controller._update_auto_sync_policy(status="ok", imported=0, manual=False)
    assert controller._sync_idle_multiplier == 2

    controller._update_auto_sync_policy(status="ok", imported=0, manual=False)
    assert controller._sync_idle_multiplier == 4

    controller._update_auto_sync_policy(status="ok", imported=2, manual=False)
    assert controller._sync_idle_multiplier == 1

    controller._update_auto_sync_policy(status="offline", imported=0, manual=False)
    assert controller._sync_idle_multiplier == 2

    controller._update_auto_sync_policy(status="auth_fail", imported=0, manual=False)
    assert controller._sync_idle_multiplier == 8


def test_controller_remote_profile_update_presence() -> None:
    controller = DugongController.__new__(DugongController)
    controller.source_id = "cornelius"
    controller._remote_presence = {}
    events = [
        DugongEvent(
            event_type="profile_update",
            source="anson",
            payload={
                "pearls": 77,
                "today_pearls": 12,
                "lifetime_pearls": 180,
                "focus_streak": 3,
                "day_streak": 2,
                "title_id": "explorer",
            },
        )
    ]
    controller._update_remote_presence(events)
    info = controller._remote_presence.get("anson", {})
    assert int(info.get("pearls", 0)) == 77
    assert str(info.get("title_id", "")) == "explorer"
