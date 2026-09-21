import urllib.error
import urllib.request

_TIMEOUT = 10.0


def post(url, body, headers):
    request = urllib.request.Request(url, data=body, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
            return response.status
    except urllib.error.HTTPError as ex:
        return ex.code
