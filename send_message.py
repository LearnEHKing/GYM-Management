"""Meta WhatsApp Cloud API sender."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _required_env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} must be set to send WhatsApp messages.")
    return value


def _timeout():
    try:
        value = int(os.environ.get("WHATSAPP_TIMEOUT_SECONDS", "15"))
    except ValueError as error:
        raise RuntimeError("WHATSAPP_TIMEOUT_SECONDS must be a positive integer.") from error
    if value <= 0:
        raise RuntimeError("WHATSAPP_TIMEOUT_SECONDS must be a positive integer.")
    return value


def _recipient(phone):
    digits = "".join(character for character in phone if character.isdigit())
    if not digits:
        raise ValueError("WhatsApp recipient must contain digits.")
    return digits


def _payload(message):
    mode = os.environ.get("WHATSAPP_MESSAGE_MODE", "template").strip().lower()
    if mode == "text":
        return {
            "messaging_product": "whatsapp",
            "type": "text",
            "text": {"preview_url": False, "body": message},
        }
    if mode == "template":
        return {
            "messaging_product": "whatsapp",
            "type": "template",
            "template": {
                "name": _required_env("WHATSAPP_TEMPLATE_NAME"),
                "language": {"code": os.environ.get("WHATSAPP_TEMPLATE_LANGUAGE", "en_US")},
                "components": [{
                    "type": "body",
                    "parameters": [{"type": "text", "text": message}],
                }],
            },
        }
    raise RuntimeError("WHATSAPP_MESSAGE_MODE must be 'template' or 'text'.")


def send_whatsapp(phone, message):
    """Send one rendered message and return Meta's accepted message ID.

    Template mode is the default because business-initiated reminders generally
    require an approved Meta template. Configure a template with one body text
    variable ({{1}}). Text mode is for an active customer-service window only.
    """
    token = _required_env("WHATSAPP_ACCESS_TOKEN")
    phone_number_id = _required_env("WHATSAPP_PHONE_NUMBER_ID")
    graph_version = os.environ.get("WHATSAPP_GRAPH_API_VERSION", "v25.0").strip()
    if not graph_version.startswith("v"):
        raise RuntimeError("WHATSAPP_GRAPH_API_VERSION must look like 'v25.0'.")
    payload = _payload(message)
    payload["to"] = _recipient(phone)
    request = Request(
        f"https://graph.facebook.com/{graph_version}/{phone_number_id}/messages",
        data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=_timeout()) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        # Do not include provider response bodies: they can contain sensitive IDs.
        raise RuntimeError(f"WhatsApp provider rejected the message (HTTP {error.code}).") from error
    except (URLError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("WhatsApp provider request failed.") from error
    try:
        return result["messages"][0]["id"]
    except (KeyError, IndexError, TypeError) as error:
        raise RuntimeError("WhatsApp provider returned an unexpected response.") from error
