import csv

from guardloop_sdk.replay import default_same, load_decisions_csv, replay

ROWS = [
    {"id": "1", "agent_name": "bot", "input_summary": "How many days in a week?", "output_summary": "7 days"},
    {"id": "2", "agent_name": "bot", "input_summary": "How many hours in a day?", "output_summary": "24 hours"},
    {"id": "3", "agent_name": "other", "input_summary": "Refund?", "output_summary": "Yes"},
]


def test_unchanged_answers_are_counted_and_changes_are_listed():
    answers = {"How many days in a week?": "7 days",
               "How many hours in a day?": "20 hours",
               "Refund?": "Yes"}
    report = replay(ROWS, agent=lambda q: answers[q])
    assert report.total == 3
    assert report.unchanged == 2
    assert report.changed == 1
    assert report.changes[0].event_id == "2"
    assert report.changes[0].before == "24 hours"
    assert report.changes[0].after == "20 hours"


def test_an_agent_crash_is_recorded_not_fatal():
    def flaky(question):
        if "week" in question:
            raise RuntimeError("model timeout")
        return "x"
    report = replay(ROWS, agent=flaky)
    assert report.errors == [("1", "RuntimeError")]
    assert report.total == 3


def test_the_comparison_can_be_replaced():
    report = replay(ROWS, agent=lambda q: "7 DAYS!!",
                    same=lambda a, b: "7" in (b or "") and "7" in (a or ""))
    assert report.changed == 2  # only row 1 mentions 7 in both; the others differ


def test_default_comparison_ignores_case_and_spacing():
    assert default_same("Use  the Link", "use the link")
    assert not default_same("yes", "no")


def test_a_limit_replays_only_the_first_rows():
    report = replay(ROWS, agent=lambda q: "x", limit=2)
    assert report.total == 2


def test_loading_a_decisions_export_filters_by_agent_and_empty_inputs(tmp_path):
    path = tmp_path / "decisions.csv"
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["id", "agent_name", "input_summary", "output_summary"])
        writer.writeheader()
        writer.writerows(ROWS + [{"id": "4", "agent_name": "bot", "input_summary": "", "output_summary": "x"}])
    loaded = load_decisions_csv(str(path), agent_name="bot")
    assert [row["id"] for row in loaded] == ["1", "2"]