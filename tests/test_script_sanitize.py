from app.agent.script_sanitize import extract_speakable_script

USER_LLM_OUTPUT = """The client is looking for a polished, 90-second narration that highlights their cloud-based business management software, specifically targeting small businesses. The narration should be professional, engaging, and informative, effectively communicating the software's features and benefits.

Now, I will create the script for the narration.

Our cloud-based business management software is designed specifically for small businesses, providing an all-in-one solution to streamline your operations. With our intuitive interface, you can easily manage your finances, track inventory, and oversee customer relationships, all from one platform.

Now, I will submit this narration for audio.

emit_audio_script({
  script: "Our cloud-based business management software is designed specifically for small businesses, providing an all-in-one solution to streamline your operations. With our intuitive interface, you can easily manage your finances, track inventory, and oversee customer relationships, all from one platform. The software is accessible from anywhere, allowing you to work on the go and stay connected with your team."
});"""


def test_extracts_script_from_emit_syntax():
    result = extract_speakable_script(USER_LLM_OUTPUT)
    assert "Our cloud-based business management software" in result
    assert "emit_audio_script" not in result
    assert "The client is looking" not in result
    assert "Now, I will" not in result


def test_filters_meta_paragraphs_without_tool_syntax():
    raw = """The client wants a short intro.

Welcome to our platform. We help small businesses grow every day."""
    result = extract_speakable_script(raw)
    assert result == "Welcome to our platform. We help small businesses grow every day."


def test_keeps_clean_narration_unchanged():
    raw = "Welcome to Acme. We built this for you."
    assert extract_speakable_script(raw) == raw
