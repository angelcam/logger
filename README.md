# README #

Simple Python logging helper with support for console, syslog, Better Stack and Loggly.

Requires Python 3.9+ and has no third-party dependencies.

### Installation ###

Just add this repo to your requirements.txt

```
git+https://github.com/angelcam/logger.git#egg=logger
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
* set_better_stack - enables async batched logging to Better Stack with the given source token and ingesting host
* set_loggly - enables async batched logging to Loggly with given token a tag
* set_syslog - enables syslog with given app_name

Better Stack and Loggly are independent: configure both and every message is
sent to both.

### Better Stack ###

Better Stack issues an **ingesting host** per source (visible in the source
settings next to the source token), so both values are required:

```
log.set_better_stack(source_token, ingesting_host)
```

Messages are buffered and sent in batches. Each record is timestamped with `dt`
at the moment it is logged, not when the batch is flushed.

### Batching ###

Both HTTP targets accept the same tuning options:

```
log.set_better_stack(token, host, max_batch_size=500, flush_interval=5.0,
                     max_queue_size=10000, max_retries=2)
```

* `max_batch_size` (500) - records per request
* `flush_interval` (5.0 s) - how long a partial batch waits before being sent
* `max_queue_size` (10000) - buffered records; when full the **oldest are dropped**,
  because logging must never block the application
* `max_retries` (2) - retries for network errors, HTTP 429 and 5xx. Other 4xx
  responses (an invalid token, say) are not retried and disable the target

Whatever is still buffered is flushed when the process exits.

Delivery is best-effort: failures are reported on stderr and never raised back
into the calling application.

### Per-class context ###

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

### Tests ###

```
python -m unittest discover -s logger/tests -t .
```

### TODO ###

* Allow different level for each handler (console, syslog, Better Stack, Loggly)
