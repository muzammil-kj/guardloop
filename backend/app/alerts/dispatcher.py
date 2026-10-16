from urllib.parse import urlparse

import requests

# The server POSTs to whatever webhook URL an organization saves, so we only
# allow the real providers' hosts and path shapes. Otherwise a user could point
# a "webhook" at an internal address and use our server to reach it (SSRF).
ALLOWED_WEBHOOKS = {
    "discord": {
        "hosts": {"discord.com", "discordapp.com", "ptb.discord.com", "canary.discord.com"},
        "path_prefix": "/api/webhooks/",
    },
    "slack": {
        "hosts": {"hooks.slack.com"},
        "path_prefix": "/services/",
    },
}


class AlertDeliveryError(Exception):
    """A webhook could not be delivered. The message never contains the URL."""


def validate_webhook_url(channel_type: str, url: str) -> None:
    rules = ALLOWED_WEBHOOKS.get(channel_type)
    if rules is None:
        raise ValueError(f"Unsupported channel type: {channel_type}")

    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("Webhook URL must start with https://")
    # .hostname ignores any user:pass@ prefix, so "discord.com@evil.com" is
    # correctly read as evil.com and rejected.
    if parsed.hostname not in rules["hosts"]:
        allowed = ", ".join(sorted(rules["hosts"]))
        raise ValueError(f"{channel_type.capitalize()} webhooks must use one of: {allowed}")
    if not parsed.path.startswith(rules["path_prefix"]):
        raise ValueError(
            f"{channel_type.capitalize()} webhook URLs must look like "
            f"https://{sorted(rules['hosts'])[0]}{rules['path_prefix']}..."
        )


def mask_webhook_url(url: str) -> str:
    """Shows enough to recognise a webhook without exposing it, e.g.
    'discord.com/...a1B2'. The full URL is never returned by the API."""
    parsed = urlparse(url)
    tail = parsed.path[-4:] if parsed.path else ""
    return f"{parsed.hostname}/...{tail}"


def _post(url: str, payload: dict) -> None:
    try:
        # allow_redirects=False: an allowed host must not bounce us elsewhere.
        response = requests.post(url, json=payload, timeout=10, allow_redirects=False)
    except requests.RequestException as exc:
        # Deliberately not chaining: requests' message includes the full URL.
        raise AlertDeliveryError(
            f"Could not reach the webhook ({type(exc).__name__})."
        ) from None

    if not response.ok:
        raise AlertDeliveryError(f"The webhook returned HTTP {response.status_code}.")


def send_discord_alert(webhook_url: str, message: str) -> None:
    _post(webhook_url, {"content": message})


def send_slack_alert(webhook_url: str, message: str) -> None:
    _post(webhook_url, {"text": message})


def send_alert(channel_type: str, webhook_url: str, message: str) -> None:
    if channel_type == "discord":
        send_discord_alert(webhook_url, message)
    elif channel_type == "slack":
        send_slack_alert(webhook_url, message)
    else:
        raise ValueError(f"Unknown alert channel type: {channel_type}")
