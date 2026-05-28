"""
Unit tests for LSLClient's metadata contract check. We don't talk to a real
LSL stream here; we feed the validator a fake inlet object that mimics the
shape of pylsl.StreamInlet just enough for the code under test.
"""

import pytest

from logic.lsl_client import LSLClient


class _FakeXmlElement:
    # Stand-in for pylsl's XML cursor. Returning an "empty" element ends a walk.
    def __init__(self, empty: bool = True):
        self._empty = empty

    def child(self, _name):
        return self

    def child_value(self, _name):
        return ""

    def next_sibling(self):
        return _FakeXmlElement(empty=True)

    def empty(self):
        return self._empty


class _FakeStreamInfo:
    def __init__(self, channel_count: int, stream_type: str):
        self._channel_count = channel_count
        self._type = stream_type

    def channel_count(self):
        return self._channel_count

    def type(self):
        return self._type

    def desc(self):
        # Returns an empty XML element so _log_channel_descriptors has
        # nothing to walk; the validator should still pass.
        return _FakeXmlElement(empty=True)


class _FakeInlet:
    def __init__(self, channel_count: int, stream_type: str):
        self._info = _FakeStreamInfo(channel_count, stream_type)

    def info(self):
        return self._info


@pytest.fixture
def client(qtbot=None):
    # No Qt event loop needed: the validator does not emit signals.
    # But constructing LSLClient still requires a QApplication-compatible env;
    # PySide6 QObject works without an event loop.
    return LSLClient()


@pytest.mark.parametrize("channel_count", [32, 33, 34])
def test_accepts_valid_channel_counts(client, channel_count):
    client.inlet = _FakeInlet(channel_count=channel_count, stream_type="NIRS")
    assert client._validate_inlet_metadata() is None


@pytest.mark.parametrize("channel_count", [0, 1, 8, 16, 31, 35, 100])
def test_rejects_wrong_channel_count(client, channel_count):
    client.inlet = _FakeInlet(channel_count=channel_count, stream_type="NIRS")
    reason = client._validate_inlet_metadata()
    assert reason is not None
    assert str(channel_count) in reason
    assert "channel count" in reason.lower()


def test_rejects_wrong_stream_type(client):
    client.inlet = _FakeInlet(channel_count=32, stream_type="EEG")
    reason = client._validate_inlet_metadata()
    assert reason is not None
    assert "type" in reason.lower()
    assert "'EEG'" in reason
    assert "'NIRS'" in reason


def test_rejects_no_inlet():
    client = LSLClient()
    client.inlet = None
    reason = client._validate_inlet_metadata()
    assert reason == "no inlet"


def test_info_call_failure_is_reported(client):
    class _Broken:
        def info(self):
            raise RuntimeError("simulated transport error")
    client.inlet = _Broken()
    reason = client._validate_inlet_metadata()
    assert reason is not None
    assert "simulated transport error" in reason
