# README #

Simple Python logging helper with support for console, syslog, Better Stack and
Loggly.

### Installation ###

Just add this repo to your requirements.txt

```
git+https://github.com/angelcam/logger.git@v2.0.0#egg=logger
```

and run

```
pip install -r requirements.txt
```

### Usage ###

```
from logger import log, INFO

log.set_min_level(INFO)
log.set_console(True)
log.set_better_stack('xxxxxxxxxxxxxxxxxxxxxxxx', 's123456.eu-nbg-2.betterstackdata.com')
log.set_loggly('xxxxxxx-yyyyy-zzzzz-yyyyy-xxxxxxx', 'app-prod')
log.set_syslog('app.py')

log.info("This is log message", camera_id=123)
```

* Default log level is DEBUG (may change in future)
* set_console - enables console logs
* set_better_stack - enables async https logging to Better Stack with the given
  source token and ingesting host
* set_loggly - enables async https logging to Loggly with given token a tag
* set_syslog - enables syslog with given app_name

Both remote targets can be enabled at the same time; every message is then sent
to both of them independently.

The source token and the ingesting host of a Better Stack source are on its
*Configuration* page, under *Basic information*. The ingesting host is specific
to each source, for example `s123456.eu-nbg-2.betterstackdata.com`.

If you need to set context per class, instantiate and use class Logger. Logging will then combine the per class context with message level one:

```
self.log = Logger.Logger(contextKey1=contextVal1)
self.log.log(log.INFO, "This is log message.")
self.log.log(log.INFO, "This is log message.", contextKey2=contextVal2)
```

You can set a class-level context to existing logger, but it will replace it, not combine with the current one:

```
self.log.set_context(foo=1,bar=2)
```

### How the remote targets work ###

Log messages never block the caller. They go to a queue that a background
thread drains as fast as the target accepts them:

* A message is **never delayed** to make a bigger batch. The sender takes
  whatever is already in the queue and posts it immediately.
* Batches are cut by size, not by count: 4 MB for Loggly, 10 MB for Better
  Stack, which is what the two endpoints accept.
* Several batches are posted concurrently (4 by default) over a connection
  pool that keeps its connections alive between batches.
* **No message is dropped** because the senders are too slow. The queue is
  unbounded, so a burst is delivered eventually rather than partially.
* A batch that fails on a network error, a 429 or a 5xx is retried three times
  with an exponential backoff. Measured against a target that answered 503 for
  three seconds, 99% of the messages survived instead of 5% without retries.
  An outage longer than the retry window still loses the batches attempted
  during it.
* Two kinds of failure are **not** retried. A 4xx other than 429 means the
  request itself is wrong, so the same request would keep failing. A timeout
  leaves the outcome unknown: the endpoint may already hold the batch, and
  neither target offers an idempotency key, so retrying would deliver those
  records twice. In both cases the target stays enabled and the loss is
  reported to stderr with the number of records.
* Whatever is still queued when the process exits is flushed before the
  interpreter shuts down. Applications with an orderly shutdown can also call
  `log.flush()` themselves; it returns `False` if the queue could not be
  delivered in time.

Both setters accept the same options if the defaults do not fit:

```
log.set_loggly(token, tag, timeout=20.0, max_tasks=4, max_queue_size=None)
```

* `timeout` - seconds to wait for a single request
* `max_tasks` - how many batches may be in flight at once
* `max_queue_size` - **opt-in** message dropping. By default the queue is
  unbounded and nothing is ever dropped, which is what applications that
  produce a lot of log messages need. Set it if you would rather lose log
  messages than let the queue grow when the target is unreachable; the number
  of dropped messages is reported to stderr.

The queue costs memory while a target is unreachable: roughly 1.5x the size of
the log messages waiting in it. Measured with every sender stalled, 200k
messages of 500 bytes grew the process by 148 MB and nothing was dropped; with
`max_queue_size=10000` the same burst grew it by 15 MB and dropped the rest.
Leave it unbounded unless an application cannot afford that, and size it from
the log volume it produces rather than from a round number.

### Running the tests ###

```
pip install aiohttp
python -m unittest discover -s logger/tests -t .
```

The library runs on Python 3.7 and newer. The test suite needs 3.8, because it
uses `unittest.IsolatedAsyncioTestCase`. The full suite was run on 3.8, 3.9,
3.10, 3.11 and 3.12; on 3.7 only a functional check of the delivery path was
run, so a regression specific to 3.7 would not be caught by CI.

### TODO ###

* Allow different level for each handler (console, syslog, Better Stack, Loggly)
