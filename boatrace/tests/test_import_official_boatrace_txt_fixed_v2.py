from scripts.import_official_boatrace_txt_fixed_v2 import find_venue


def test_venue_is_only_detected_in_header() -> None:
    assert find_venue("1 3434松尾宣邦57福岡56B1 4.32 23.16") is None
    assert find_venue("ボートレース唐 津 7月12日") is not None
