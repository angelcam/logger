# README #

Simple Python logging helper with support for console, syslog and Loggly.

### Installation ###

Just add this repo to your requirements.txt

```
git+https://github.com/angelcam/logger.git@v1.1.6#egg=logger
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
log.set_loggly('xxxxxxx-yyyyy-zzzzz-yyyyy-xxxxxxx', 'app-prod')
log.set_syslog('app.py')

log.info("This is log message", camera_id=123)
```

* Default log level is DEBUG (may change in future)
* set_console - enables console logs
* set_loggly - enables async https logging to Loggly with given token a tag
* set_syslog - enables syslog with given app_name

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

### TODO ###

* Allow different level for each handler (console, syslog, Loggly)
