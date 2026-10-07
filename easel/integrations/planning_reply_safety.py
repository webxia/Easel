"""Check raw structured replies before any durable content capture.

This is a storage safety check, not semantic admission. Invalid or sensitive
responses retain only their classification; their raw content is not saved.
"""
import json

from easel.integrations.hypit.secrets import SecretRedactor


def safe_structured_text(text):
    try:
        text.encode('utf-8')
        if SecretRedactor.contains_secret(text):
            return False
        def checked_object(pairs):
            result = {}
            for key, value in pairs:
                # Inspect each decoded pair before duplicate keys can hide it.
                if SecretRedactor.contains_secret(value, parent_key=key) or key in result:
                    raise ValueError('Unsafe structured response')
                result[key] = value
            return result
        def invalid_constant(_):
            raise ValueError('Invalid structured response')
        value = json.loads(text, object_pairs_hook=checked_object,
                           parse_constant=invalid_constant)
        return isinstance(value, dict) and not SecretRedactor.contains_secret(value)
    except (ValueError, UnicodeError, RecursionError, TypeError):
        return False
