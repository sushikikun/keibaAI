from scripts.import_official_boatrace_txt_fixed import (
    base,
    parse_program_entry,
    parse_trifecta_payout,
)


def test_fixed_program_entry() -> None:
    row = parse_program_entry(
        base.norm_line(
            "1 4798浜先真範33広島53A1 6.26 41.74 6.88 46.15 54 33.33 6 42.17"
        )
    )
    assert row is not None
    assert (row["lane"], row["racer_id"], row["racer_name"]) == (1, "4798", "浜先真範")
    assert (row["age"], row["branch"], row["weight_kg"], row["grade"]) == (
        33,
        "広島",
        53.0,
        "A1",
    )
    assert row["national_win_rate_snapshot"] == 6.26
    assert row["boat_top2_rate_snapshot"] == 42.17


def test_result_and_payout_rows() -> None:
    result = base.parse_result_entry(base.norm_line("01 1 4798 浜 先 真 範 54 6 6.69"))
    assert result == {"finish_position": 1, "lane": 1, "racer_id": "4798"}
    payout = parse_trifecta_payout(base.norm_line("3連単 1-5-4 1550 人気 10"))
    assert payout is not None
    assert (payout["combo"], payout["payout_yen"]) == ("1-5-4", 1550)
