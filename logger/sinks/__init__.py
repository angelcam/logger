import datetime


def utcnow():
    """The current time as an RFC 3339 string, which both targets accept."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()
