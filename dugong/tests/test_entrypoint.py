from dugong_app.main import create_default_controller


def test_entrypoint_exports_controller_factory() -> None:
    controller = create_default_controller()
    assert controller is not None
