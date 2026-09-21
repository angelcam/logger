import urllib.error
import urllib.request

def post(url, body, headers, timeout=5.0):
    request = urllib.request.Request(url, data=body, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status
    except urllib.error.HTTPError as ex:
        return ex.code
