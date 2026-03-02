import re

TCO_LENGTH = 23  # t.co URLs are always 23 chars


def twitter_length(text: str) -> int:
    """Calculate Twitter character count, accounting for t.co URL wrapping."""
    url_pattern = re.compile(r"https?://\S+")
    length = len(text)
    for match in url_pattern.finditer(text):
        url_len = len(match.group())
        length = length - url_len + TCO_LENGTH
    return length


def twitter_truncate(text: str, limit: int = 280) -> str:
    """Truncate text to fit within Twitter's character limit.

    Tries to break at sentence boundary, then word boundary.
    Accounts for t.co URL lengths.
    """
    if twitter_length(text) <= limit:
        return text

    # Split into lines to preserve structure
    lines = text.split("\n")
    result = []
    for line in lines:
        candidate = "\n".join(result + [line])
        if twitter_length(candidate) <= limit:
            result.append(line)
        else:
            # Try to fit partial line
            words = line.split()
            partial = []
            for word in words:
                test = "\n".join(result + [" ".join(partial + [word])])
                if twitter_length(test) <= limit - 1:  # room for ellipsis
                    partial.append(word)
                else:
                    break
            if partial:
                result.append(" ".join(partial) + "…")
            elif not result:
                # Nothing fits — hard truncate
                result.append(line[: limit - 1] + "…")
            break

    return "\n".join(result)
