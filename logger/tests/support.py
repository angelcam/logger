import threading
import time


class FakeTransport(object):

    def __init__(self, fail_times=0, error=None):
        self.batches = []
        self._lock = threading.Lock()
        self._fail_times = fail_times
        self._error = error or RuntimeError("transport boom")
        self.attempts = 0

    def __call__(self, records):
        with self._lock:
            self.attempts += 1
            should_fail = self.attempts <= self._fail_times
            if not should_fail:
                self.batches.append(list(records))
        if should_fail:
            raise self._error

    def wait_for_batches(self, count, timeout=2.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                if len(self.batches) >= count:
                    return True
            time.sleep(0.005)
        return False


class BlockingTransport(object):

    def __init__(self):
        self.batches = []
        self.entered = threading.Event()
        self.release = threading.Event()
        self._lock = threading.Lock()

    def __call__(self, records):
        self.entered.set()
        self.release.wait(2.0)
        with self._lock:
            self.batches.append(list(records))

    def delivered_messages(self):
        with self._lock:
            return [r['message'] for batch in self.batches for r in batch]


class FakeHttp(object):

    def __init__(self, status=202):
        self.status = status
        self.calls = []
        self._lock = threading.Lock()

    def __call__(self, url, body, headers):
        with self._lock:
            self.calls.append((url, body, headers))
        return self.status

    def wait_for_calls(self, count, timeout=2.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                if len(self.calls) >= count:
                    return True
            time.sleep(0.005)
        return False
