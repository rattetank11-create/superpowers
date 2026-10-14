import pandas as pd
import pytest

from analysis.errors import LegacyDemoError, NotADemoError
from analysis.loader import _steamid, assign_rounds, build_rounds, check_demo_header


class TestHeader:
    def test_cs2_ok(self):
        check_demo_header(b"PBDEMS2\x00" + b"\x00" * 8)

    def test_csgo_rejected_with_specific_error(self):
        with pytest.raises(LegacyDemoError):
            check_demo_header(b"HL2DEMO\x00" + b"\x00" * 8)

    def test_random_file_rejected(self):
        with pytest.raises(NotADemoError):
            check_demo_header(b"PK\x03\x04 zip file")


def test_steamid_keeps_precision():
    s = _steamid(pd.Series(["76561197964020430", None, "0", "garbage"]))
    assert s.iloc[0] == 76561197964020430
    assert s.iloc[1:].isna().all()


def test_build_rounds_skips_warmup_and_pre_match():
    fe = pd.DataFrame(
        {"tick": [50, 1000, 3000], "is_warmup_period": [True, False, False], "total_rounds_played": [0, 0, 1]}
    )
    re_ = pd.DataFrame({"tick": [2500, 4000], "winner": [2, 3]})
    rounds = build_rounds(fe, re_, match_start_tick=100)
    assert rounds["round_num"].tolist() == [1, 2]
    assert rounds["end_tick"].tolist() == [2500, 4000]
    assert rounds["winner"].tolist() == [2, 3]


def test_assign_rounds():
    rounds = pd.DataFrame({"round_num": [1, 2], "start_tick": [100, 200]})
    out = assign_rounds(pd.Series([50, 100, 150, 250]), rounds)
    assert out.isna().iloc[0]
    assert out.iloc[1:].tolist() == [1, 1, 2]
