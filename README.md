# Logbook-logstash


## Why this?
It's really necessary to build a centralized log system, especially when you have migrated your business to kubernetes-based distributed architecture. Our choice is ELK stack. Since we are already using Logbook, a great alternative to Python's built-in `logging` module, I need to connect Logbook with Logstash. You could use Redis as a broker between them, and there is actually a `RedisHandler` to help you do that. But this needs `redis` package to be required in every micro services. I want a more lightweight solution. So I write a `LogstashHandler` based on TCP socket.

## Features
- Reliable connection (reconnect if connection is down)
- Thread-safe (by using thread-safe queue `collection.deque`)
- Record contextual information (see example below)

## Usage
1. Add this module to your project as a git submodule (I'm not planning to publish this module to PyPI, since a package would be hard to meet everyone's need. You can fork and do your own customization using submodule): 

    ```git submodule add https://github.com/fr0der1c/logbook_logstash.git```
1. Add a pipeline in Logstash:
    ```
    input {
      tcp {
        port => 10000
        mode => server
        tcp_keep_alive => true
        codec => json
      }
    }
    filter {
      mutate {
        remove_field => [ "host", "port" ]
        add_field => { "environment" => "production" }
      }
    }
    output {
      elasticsearch {
        hosts => "https://your.elasticsearch.com"
        index => "some-log-%{+YYYY.MM.dd}"
      }
    }
    ```
1. In your app:
    ```
    logger = logbook.Logger(__name__)
    logstash_handler = LogstashHandler(host=app.config['LOGSTASH']['HOST'],
                                       port=app.config['LOGSTASH']['PORT'],
                                       release=app.config['GIT_DESCRIBE'],
                                       logger=logger)
    logger.handlers.append(logstash_handler)
    ```
1. You're all set. 

## Example log item
Here is a example log item:
```json
{
  "_index": "everyclass-server-log-2018.11.10",
  "_type": "doc",
  "_id": "wJwP_mYBgAiLc452vBh6",
  "_score": 1,
  "_source": {
    "@version": "1",
    "message": "App created with `production` config",
    "context": {
      "lineno": 146,
      "kwargs": {
        "stack": false
      },
      "thread": 139863313599368,
      "exception_message": null,
      "thread_name": "uWSGIWorker2Core0",
      "formatted_exception": null,
      "func_name": "create_app",
      "greenlet": 139863313599368,
      "extra": {},
      "filename": "/var/everyclass-server/everyclass/server/__init__.py",
      "args": [],
      "process_name": "MainProcess",
      "module": "everyclass.server",
      "frame_correction": 0,
      "exception_name": null,
      "process": 2468
    },
    "source_host": "everyclass-server-766d764787-4r68x",
    "environment": "production",
    "release": "v0.9.19",
    "@timestamp": "2018-11-10T14:38:50.897Z",
    "logger": "everyclass.server",
    "level": "INFO"
  },
  "fields": {
    "@timestamp": [
      "2018-11-10T14:38:50.897Z"
    ]
  }
}
```