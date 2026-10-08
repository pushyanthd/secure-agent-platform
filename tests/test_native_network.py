import runpy
from pathlib import Path

import pytest

ADDRESS = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "scripts/pc/summarize_native_network.py")
)["address"]


@pytest.mark.parametrize(
    "value,expected",
    [
        ("127.0.0.1:8101", "127.0.0.1"),
        ("127.0.0.1", "127.0.0.1"),
        ("[::1]:8101", "::1"),
        ("::1", "::1"),
        ("0.0.0.0", "0.0.0.0"),
        ("203.0.113.1:443", "203.0.113.1"),
    ],
)
def test_etw_socket_address_retains_actual_ip(value, expected):
    assert ADDRESS(value) == expected


def test_unknown_address_cannot_be_silently_classified_as_loopback():
    with pytest.raises(ValueError):
        ADDRESS("unknown socket")


def test_kernel_header_context_is_not_network_connection_ownership(tmp_path):
    import csv
    import hashlib
    import json

    module = runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "scripts/pc/summarize_native_network.py")
    )
    (tmp_path / "observation.json").write_text(
        json.dumps(
            {
                "model_pid": 4032,
                "trace_sha256": hashlib.sha256(b"synthetic").hexdigest(),
                "start_utc": "synthetic",
                "end_utc": "synthetic",
            }
        )
    )
    (tmp_path / "network.etl").write_bytes(b"synthetic")
    (tmp_path / "provider-schemas.json").write_text(
        json.dumps(
            {
                "1017:1": ["ProcessId", "RemoteAddress"],
                "1332:5": ["RemoteAddress"],
            }
        )
    )
    (tmp_path / "trace-summary.txt").write_text("Total Events Lost 0\n")
    header = (
        "Event Name,Type,Event ID,Version,Channel,Level,Opcode,Task,Keyword,PID,TID,"
        "Processor Number,Instance ID,Parent Instance ID,Activity ID,Related Activity ID,"
        "Clock-Time,Kernel(ms),User(ms),User Data"
    )
    with (tmp_path / "events.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(header.split(","))
        for event, version, data in [
            ("1017", "1", ["4032", "127.0.0.1:8101"]),
            ("1017", "1", ["18976", "203.0.113.1:443"]),
            ("1332", "5", ["203.0.113.1:443"]),
        ]:
            base = ["Microsoft-Windows-TCPIP", "Info", event, version] + ["0"] * 15
            base[9] = "0x00000FC0"
            base[16] = "134359564728506779"
            writer.writerow(base + data)
    result = module["summarize"](tmp_path)
    assert result["passed"] is True
    assert result["model_events"] == 1
    assert result["excluded_unowned_header_context_events"] == 2
    assert result["nonloopback_remote_endpoints"] == []
