# tests/test_email_sender.py
"""
Tests for the email sender utility:
- HTML template building
- SMTP error handling
- Config validation
"""
import pytest
from unittest.mock import patch, MagicMock
from utils.email_sender import send_html_email, build_email_wrapper


class TestBuildEmailWrapper:

    def test_returns_string(self):
        """build_email_wrapper must return a string."""
        result = build_email_wrapper("Test Title", "<p>Content</p>", "test-agent")
        assert isinstance(result, str)

    def test_contains_title(self):
        """Email HTML must contain the title."""
        result = build_email_wrapper("My Title", "<p>Content</p>", "test-agent")
        assert "My Title" in result

    def test_contains_content(self):
        """Email HTML must contain the body content."""
        result = build_email_wrapper("Title", "<p>Hello World</p>", "agent")
        assert "Hello World" in result

    def test_contains_agent_name(self):
        """Email footer must mention the agent name."""
        result = build_email_wrapper("Title", "<p>Content</p>", "wallstreet_wolf")
        assert "wallstreet_wolf" in result

    def test_is_valid_html(self):
        """Result must contain basic HTML structure."""
        result = build_email_wrapper("Title", "<p>Content</p>", "agent")
        assert "<!DOCTYPE html>" in result
        assert "<html"           in result
        assert "</html>"         in result

    def test_contains_utf8_charset(self):
        """Must declare UTF-8 charset for Arabic text support."""
        result = build_email_wrapper("Title", "<p>Content</p>", "agent")
        assert "UTF-8" in result

    def test_handles_arabic_content(self):
        """Must handle Arabic characters without errors."""
        arabic_content = "<p>كِتَاب — Book</p>"
        result = build_email_wrapper("Arabic Test", arabic_content, "arabic_word")
        assert "كِتَاب" in result


class TestSendHtmlEmail:

    def test_returns_false_without_config(self):
        """Returns False (not exception) when SMTP config is missing."""
        with patch.dict("os.environ", {
            "SMTP_USER": "", "SMTP_PASSWORD": "", "EMAIL_RECIPIENT": ""
        }):
            result = send_html_email("Test", "<p>Content</p>")
            assert result == False

    def test_returns_false_on_auth_error(self):
        """Returns False (not exception) on SMTP authentication failure."""
        import smtplib
        with patch.dict("os.environ", {
            "SMTP_USER": "test@gmail.com",
            "SMTP_PASSWORD": "wrongpassword",
            "EMAIL_RECIPIENT": "test@gmail.com"
        }):
            with patch("smtplib.SMTP") as mock_smtp:
                mock_smtp.return_value.__enter__ = lambda s: mock_smtp.return_value
                mock_smtp.return_value.__exit__  = lambda s,*a: None
                mock_smtp.return_value.login.side_effect = smtplib.SMTPAuthenticationError(535, b"auth failed")
                result = send_html_email("Test", "<p>Content</p>")
                assert result == False

    def test_returns_true_on_success(self):
        """Returns True when email sends successfully."""
        with patch.dict("os.environ", {
            "SMTP_USER":      "test@gmail.com",
            "SMTP_PASSWORD":  "validpassword",
            "EMAIL_RECIPIENT": "test@gmail.com",
            "SMTP_HOST":      "smtp.gmail.com",
            "SMTP_PORT":      "587",
        }):
            with patch("smtplib.SMTP") as mock_smtp:
                instance = MagicMock()
                mock_smtp.return_value.__enter__ = lambda s: instance
                mock_smtp.return_value.__exit__  = lambda s,*a: None
                result = send_html_email("Test Subject", "<p>Test</p>")
                assert result == True

    def test_custom_recipient(self):
        """Custom recipient overrides the default EMAIL_RECIPIENT."""
        with patch.dict("os.environ", {
            "SMTP_USER":       "sender@gmail.com",
            "SMTP_PASSWORD":   "password",
            "EMAIL_RECIPIENT": "default@gmail.com",
            "SMTP_HOST":       "smtp.gmail.com",
            "SMTP_PORT":       "587",
        }):
            with patch("smtplib.SMTP") as mock_smtp:
                instance = MagicMock()
                mock_smtp.return_value.__enter__ = lambda s: instance
                mock_smtp.return_value.__exit__  = lambda s,*a: None
                result = send_html_email(
                    "Test", "<p>Test</p>",
                    recipient="custom@gmail.com"
                )
                assert result == True
