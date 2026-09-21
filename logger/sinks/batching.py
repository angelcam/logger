import atexit
import queue
import sys
import threading
import time

# worker wake-up interval to keep stop() responsive
_POLL_INTERVAL = 0.02

# rate limit for the 'queue full' stderr warning
_DROP_REPORT_INTERVAL = 10.0


class NonRetryableError(Exception):
    """Raised when retrying is futile, e.g., due to a rejected token."""


def _report(message):
    print('logger: %s' % message, file=sys.stderr)


class BatchingSender(object):
    """Batches records and sends them to a transport in a background thread."""

    def __init__(self, transport, max_batch_size=500, flush_interval=5.0,
                 max_queue_size=10000, max_retries=2, retry_backoff=0.5):
        self._transport = transport
        self._max_batch_size = max_batch_size
        self._flush_interval = flush_interval
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff
        self._queue = queue.Queue(maxsize=max_queue_size)
        self._stopping = threading.Event()
        self._disabled = False
        self._dropped = 0
        self._last_drop_report = 0.0
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

        atexit.register(self.stop)

    @property
    def queue_size(self):
        return self._queue.qsize()

    @property
    def dropped_count(self):
        return self._dropped

    def send(self, record):
        if self._disabled:
            return

        while True:
            try:
                self._queue.put_nowait(record)
                return
            except queue.Full:
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    pass
                else:
                    self._dropped += 1
                    self._report_drops()

    def _report_drops(self):
        now = time.monotonic()
        if now - self._last_drop_report < _DROP_REPORT_INTERVAL:
            return
        self._last_drop_report = now
        _report('queue full, dropped %d records so far' % self._dropped)

    def stop(self, timeout=3.0):
        self._stopping.set()
        self._worker.join(timeout)

    def _run(self):
        while not self._stopping.is_set():
            batch = self._collect()
            if batch:
                self._deliver(batch)
        self._drain()

    def _drain(self):
        """Deliver whatever is left in the queue before the worker exits."""
        while not self._disabled:
            batch = []
            while len(batch) < self._max_batch_size:
                try:
                    batch.append(self._queue.get_nowait())
                except queue.Empty:
                    break
            if not batch:
                return
            self._deliver(batch)

    def _deliver(self, batch):
        for attempt in range(self._max_retries + 1):
            try:
                self._transport(batch)
                return
            except NonRetryableError as ex:
                _report('disabling this target: %s' % ex)
                self._disabled = True
                return
            except Exception:
                if attempt == self._max_retries:
                    _report('dropping a batch of %d records after %d attempts'
                            % (len(batch), attempt + 1))
                    return
                self._stopping.wait(self._retry_backoff * (2 ** attempt))

    def _collect(self):
        batch = []
        deadline = None

        while not self._stopping.is_set() and len(batch) < self._max_batch_size:
            if deadline is None:
                timeout = _POLL_INTERVAL
            else:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                timeout = min(remaining, _POLL_INTERVAL)

            try:
                batch.append(self._queue.get(timeout=timeout))
            except queue.Empty:
                continue

            if deadline is None:
                deadline = time.monotonic() + self._flush_interval

        return batch
