import re
import unicodedata


MAX_LENGTH = 3000

BLOCKED_TERMS = {
    "fuck",
    "gay",
    "nigger",
    "nigga",
    "niga",
    "pussy",
    "dick",
    "penis",
    "motherfucker",
    "mf",
    "dickhead",
    "dumbass",
    "ass",
    "dumbfuck",
    "smartass",
    "bitch",
    "fck",
    "mkc",
    "mc",
    "madarchod",
    "behenchod",
    "bhenchod",
    "bkc",
    "chutiya",
    "chutia",
    "saala",
    "sala",
    "chut",
    "chootiya",
    "chootiye",
    "chutiye",
    "laude",
    "lulli",
    "lund"
}


CHARACTER_MAP = str.maketrans({
    "0": "o",
    "1": "i",
    "3": "e",
    "4": "a",
    "5": "s",
    "7": "t",
    "@": "a",
    "$": "s",
})


def normalize_text(text):
    text = unicodedata.normalize(
        "NFKC",
        text
    )

    text = text.lower()

    text = text.translate(
        CHARACTER_MAP
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def normalize_for_moderation(text):
    text = normalize_text(text)

    text = re.sub(
        r"[\W_]+",
        "",
        text
    )

    return text


def contains_blocked_term(text):
    normal = normalize_text(text)
    moderation = normalize_for_moderation(text)

    for term in BLOCKED_TERMS:
        term_normal = normalize_text(term)
        term_moderation = normalize_for_moderation(term)

        if re.search(
            rf"(?<!\w){re.escape(term_normal)}(?!\w)",
            normal
        ):
            return True

        if term_moderation in moderation:
            return True

    return False


def contains_spam(text):
    normalized = normalize_text(text)

    if len(normalized) > MAX_LENGTH:
        return True

    if re.search(
        r"(.)\1{8,}",
        normalized
    ):
        return True

    words = normalized.split()

    if len(words) >= 10:
        repeated = max(
            words.count(word)
            for word in set(words)
        )

        if repeated / len(words) >= 0.7:
            return True

    return False


def validate_content(text):
    if not text or not text.strip():
        return False, "Content cannot be empty."

    if len(text.strip()) > MAX_LENGTH:
        return False, (
            f"Content cannot exceed "
            f"{MAX_LENGTH} characters."
        )

    if contains_blocked_term(text):
        return False, (
            "Your content contains "
            "language that is not allowed."
        )

    if contains_spam(text):
        return False, (
            "Your content appears to be spam."
        )

    return True, None