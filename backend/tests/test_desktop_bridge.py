"""Desktop bridge keeps Blender operations on the thread draining its queue."""

import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest


def test_desktop_bridge_dispatches_on_main_thread_and_returns_model():
    from blender_worker.desktop_http import DesktopBridge

    calls = []
    bridge = DesktopBridge(lambda path, params: (calls.append((threading.get_ident(), path, params)) or b"glTF", "model/gltf-binary"), port=0)
    bridge.start()
    response = []

    def request_model():
        req = Request(bridge.url + "/figure.glb", data=json.dumps({"height_cm": 185}).encode(), headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=5) as r:
            response.append((r.read(), r.headers["Content-Type"]))

    client = threading.Thread(target=request_model)
    try:
        client.start()
        assert bridge.pending.wait(3)
        assert not calls  # HTTP thread must never touch Blender.
        bridge.drain()
        client.join(3)
        assert response == [(b"glTF", "model/gltf-binary")]
        assert calls == [(threading.get_ident(), "/figure.glb", {"height_cm": 185})]
        with urlopen(bridge.url + "/health") as r:
            assert json.load(r)["mode"] == "desktop"
    finally:
        bridge.stop()


@pytest.mark.parametrize("headers,body,code", [
    ({"Content-Type": "application/json", "Origin": "http://example.com"}, b"{}", 403),
    ({"Content-Type": "text/plain"}, b"{}", 415),
    ({"Content-Type": "application/json"}, b"invalid", 422),
    ({"Content-Type": "application/json"}, b"[]", 422),
])
def test_desktop_bridge_rejects_browser_and_malformed_requests(headers, body, code):
    from blender_worker.desktop_http import DesktopBridge

    bridge = DesktopBridge(lambda *_: pytest.fail("Invalid request reached Blender"), port=0)
    bridge.start()
    try:
        with pytest.raises(HTTPError) as error:
            urlopen(Request(bridge.url + "/figure.glb", data=body, headers=headers), timeout=3)
        assert error.value.code == code
        assert not bridge.pending.is_set()
    finally:
        bridge.stop()
