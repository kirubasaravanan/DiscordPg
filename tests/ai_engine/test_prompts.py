"""Pure string-building — no Ollama, no network, needed for these."""

import prompts


def test_classification_messages_includes_description_as_final_user_message():
    messages = prompts.classification_messages("The wifi is down.")

    assert messages[0]["role"] == "system"
    assert messages[-1] == {"role": "user", "content": "The wifi is down."}


def test_classification_messages_system_prompt_lists_all_categories_and_priorities():
    messages = prompts.classification_messages("anything")
    system = messages[0]["content"]

    for category in prompts.CLASSIFICATION_CATEGORIES:
        assert category in system
    for priority in prompts.CLASSIFICATION_PRIORITIES:
        assert priority in system


def test_summary_messages_embeds_stats_as_json():
    messages = prompts.summary_messages({"occupancy": {"total_beds": 12}})

    assert '"total_beds": 12' in messages[-1]["content"]


def test_answer_messages_includes_question_and_labeled_context():
    messages = prompts.answer_messages(
        "When is rent due?",
        [{"source": "pg_rules.md", "content": "Rent is due on the 5th."}],
    )

    user_content = messages[-1]["content"]
    assert "When is rent due?" in user_content
    assert "[pg_rules.md]" in user_content
    assert "Rent is due on the 5th." in user_content


def test_answer_messages_with_multiple_context_chunks_labels_each():
    messages = prompts.answer_messages(
        "question",
        [
            {"source": "a.md", "content": "content a"},
            {"source": "b.md", "content": "content b"},
        ],
    )

    user_content = messages[-1]["content"]
    assert "[a.md]" in user_content
    assert "[b.md]" in user_content
