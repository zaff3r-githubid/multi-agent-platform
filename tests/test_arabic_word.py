# tests/test_arabic_word.py
"""
Tests for the Arabic Word of the Day agent:
- Word list completeness
- SRS logic
- Agent configuration
"""
import pytest
from utils.arabic_word_lists import BEGINNER_WORDS, INTERMEDIATE_WORDS, ADVANCED_WORDS, ALL_WORDS
from agents.arabic_word import ArabicWordAgent


class TestWordLists:

    def test_beginner_list_has_words(self):
        """Beginner list must have at least 10 words."""
        assert len(BEGINNER_WORDS) >= 10

    def test_intermediate_list_has_words(self):
        """Intermediate list must have at least 10 words."""
        assert len(INTERMEDIATE_WORDS) >= 10

    def test_advanced_list_has_words(self):
        """Advanced list must have at least 10 words."""
        assert len(ADVANCED_WORDS) >= 10

    def test_all_words_dict_has_three_levels(self):
        """ALL_WORDS must contain all three difficulty levels."""
        assert "beginner"     in ALL_WORDS
        assert "intermediate" in ALL_WORDS
        assert "advanced"     in ALL_WORDS

    def test_word_tuples_have_five_fields(self):
        """Each word entry must have 5 fields: word, transliteration, root, root_trans, verse_ref."""
        for word_tuple in BEGINNER_WORDS:
            assert len(word_tuple) == 5, f"Word tuple has wrong length: {word_tuple}"

    def test_verse_refs_have_correct_format(self):
        """Verse references must be in format 'surah:ayah'."""
        for word_tuple in BEGINNER_WORDS + INTERMEDIATE_WORDS + ADVANCED_WORDS:
            verse_ref = word_tuple[4]
            assert ":" in verse_ref, f"Invalid verse ref: {verse_ref}"
            parts = verse_ref.split(":")
            assert len(parts) == 2
            assert parts[0].isdigit(), f"Surah number not digit: {verse_ref}"
            assert parts[1].isdigit(), f"Ayah number not digit: {verse_ref}"

    def test_no_empty_words(self):
        """No word entry should have empty Arabic text."""
        for word_tuple in BEGINNER_WORDS:
            assert word_tuple[0].strip() != "", "Empty Arabic word found"

    def test_known_words_in_beginner_list(self):
        """Key Quranic words must be in the beginner list."""
        beginner_words = [w[0] for w in BEGINNER_WORDS]
        assert "الله"   in beginner_words  # Allah
        assert "رَبّ"   in beginner_words  # Rabb
        assert "كِتَاب" in beginner_words  # Kitab


class TestArabicWordAgent:

    def test_agent_name(self):
        """Agent must identify as arabic_word."""
        agent = ArabicWordAgent()
        assert agent.name == "arabic_word"

    def test_srs_intervals_defined(self):
        """SRS box intervals must be defined for all 3 boxes."""
        agent = ArabicWordAgent()
        assert 1 in agent.SRS_INTERVALS
        assert 2 in agent.SRS_INTERVALS
        assert 3 in agent.SRS_INTERVALS

    def test_srs_intervals_increasing(self):
        """Higher SRS boxes must have longer review intervals."""
        agent = ArabicWordAgent()
        assert agent.SRS_INTERVALS[1] < agent.SRS_INTERVALS[2]
        assert agent.SRS_INTERVALS[2] < agent.SRS_INTERVALS[3]

    def test_initial_status(self):
        """Agent starts in never_run state."""
        agent = ArabicWordAgent()
        s = agent.status()
        assert s["last_status"] == "never_run"
        assert s["crash_count"] == 0

    def test_inherits_base_agent(self):
        """ArabicWordAgent must inherit from BaseAgent."""
        from agents.base_agent import BaseAgent
        assert isinstance(ArabicWordAgent(), BaseAgent)

    def test_has_update_srs_method(self):
        """Agent must have the update_srs method for dashboard interaction."""
        agent = ArabicWordAgent()
        assert hasattr(agent, "update_srs")
        assert callable(agent.update_srs)

    def test_difficulty_setting_defaults_to_beginner(self):
        """Default difficulty must be beginner."""
        import os
        os.environ.pop("ARABIC_DIFFICULTY", None)  # Remove if set
        agent = ArabicWordAgent()
        difficulty = agent._get_difficulty_setting()
        assert difficulty == "beginner"

    def test_difficulty_setting_reads_env(self):
        """Difficulty setting must read from environment variable."""
        import os
        os.environ["ARABIC_DIFFICULTY"] = "advanced"
        agent = ArabicWordAgent()
        difficulty = agent._get_difficulty_setting()
        assert difficulty == "advanced"
        os.environ.pop("ARABIC_DIFFICULTY", None)  # Cleanup
