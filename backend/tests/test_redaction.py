from app.privacy.redaction import redact


def test_email_is_masked():
    result = redact("Write to jane.doe@example.com today")
    assert result.text == "Write to [EMAIL] today"
    assert result.counts == {"EMAIL": 1}


def test_pakistani_international_phone_is_masked():
    assert redact("Call +92 300 1234567 now").text == "Call [PHONE] now"


def test_local_mobile_number_is_masked():
    assert redact("My number is 03001234567").text == "My number is [PHONE]"


def test_a_valid_card_number_is_masked():
    assert redact("Card 4111 1111 1111 1111 declined").text == "Card [CARD] declined"


def test_a_number_failing_the_luhn_check_is_not_called_a_card():
    text = "ref 4111 1111 1111 1112"
    assert "[CARD]" not in redact(text).text


def test_pakistani_cnic_is_masked():
    assert redact("CNIC 35202-1234567-8").text == "CNIC [CNIC]"


def test_us_social_security_number_is_masked():
    assert redact("SSN 123-45-6789").text == "SSN [SSN]"


def test_amounts_dates_and_short_ids_are_left_alone():
    text = "Invoice 4921 for $14,200 due 2026-10-25"
    assert redact(text).text == text
    assert redact(text).changed is False


def test_multiple_items_are_counted():
    result = redact("a@b.co and c@d.co")
    assert result.text == "[EMAIL] and [EMAIL]"
    assert result.counts == {"EMAIL": 2}


def test_none_and_empty_input_are_safe():
    assert redact(None).text == ""
    assert redact("").changed is False