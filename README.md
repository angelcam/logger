# README #

Simple Python logging helper with support for console, syslog and Loggly.

### Installation ###

Just add this repo to your requirements.xt

```
-e git+https://bitbucket.org/angelcam/logger.git#egg=logger
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

If yout need to set context per class, instantiate and use class Logger

```
self.log = Logger.Logger({"contextKey1", contextVal1})
self.log.log(log.INFO, "This is log message.")
self.log.log(log.INFO, "This is log message.", contextKey2=contextVal2)
```

### TODO ###

* Allow different level for each handler (console, syslog, Loggly)
