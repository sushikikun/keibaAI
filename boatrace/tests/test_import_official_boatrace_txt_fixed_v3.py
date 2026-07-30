from scripts.import_official_boatrace_txt_fixed_v3 import find_venue


def test_normalized_venue_header_and_branch_row() -> None:
    assert find_venue("1 3434松尾宣邦57福岡56B1 4.32 23.16") is None
    assert find_venue("ボ-トレ-ス唐 津 7月12日") is not None
