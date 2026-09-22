import atexit

from .executor import BatchExecutor, SinkThread
from .transport import HttpTransport

EXIT_FLUSH_TIMEOUT = 5.0


class Sink:
    """A logging target that sends records in batches from a separate thread."""

    def __init__(self, url, headers, encode, max_size, timeout=20.0,
                 max_tasks=4, max_queue_size=None):
        self.__encode = encode

        def create_executor():
            return BatchExecutor(
                HttpTransport(url, headers, timeout),
                max_size=max_size,
                max_tasks=max_tasks,
                max_queue_size=max_queue_size,
            )

        self.__thread = SinkThread(create_executor)
        self.__thread.start()

        atexit.register(self.flush)

    def send(self, record):
        self.__thread.send(self.__encode(record))

    def flush(self, timeout=EXIT_FLUSH_TIMEOUT):
        return self.__thread.flush(timeout)
