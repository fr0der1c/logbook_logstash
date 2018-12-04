"""
`LogstashFormatter` is from https://github.com/seatrade/logbook-logstash
"""
import datetime
import json
import socket
import traceback as tb

LOG_FORMAT_STRING = '[{record.time:%Y-%m-%d %H:%M:%S}] [{record.module}] ' \
                    '[{record.level_name}]: {record.message}'


def _default_json_default(obj):
    """
    Coerce everything to strings.
    All objects representing time get output as ISO8601.
    """
    if isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
        return obj.isoformat()
    else:
        return str(obj)


class LogstashFormatter(object):
    """
    A custom formatter to prepare logs to be
    shipped out to logstash.
    """

    def __init__(self,
                 fmt=None,
                 datefmt=None,
                 json_cls=None,
                 json_default=_default_json_default,
                 enable_handler_fields=False,
                 release=None):
        """
        :param fmt: Config as a JSON string, allowed fields;
               extra: provide extra fields always present in logs
               source_host: override source host name
        :param datefmt: Date format to use (required by logging.Formatter
            interface but not used)
        :param json_cls: JSON encoder to forward to json.dumps
        :param json_default: Default JSON representation for unknown types,
                             by default coerce everything to a string
        """

        if fmt is not None:
            self._fmt = json.loads(fmt)
        else:
            self._fmt = {}
        self.json_default = json_default
        self.json_cls = json_cls
        if 'extra' not in self._fmt:
            self.defaults = {}
        else:
            self.defaults = self._fmt['extra']
        if 'source_host' in self._fmt:
            self.source_host = self._fmt['source_host']
        else:
            try:
                self.source_host = socket.gethostname()
            except BaseException:
                self.source_host = ""

        self.enable_handler_fields = enable_handler_fields

        self.release = release

    def __call__(self, record, handler):
        """
        Format a log record to JSON, if the message is a dict
        assume an empty message and use the dict as additional
        fields.
        """

        fields = record.to_dict()
        fields['level_name'] = record.level_name

        # Extract `msg` from `fields`
        if isinstance(record.msg, dict):
            fields.update(record.msg)
            fields.pop('msg')
            msg = ""
        else:
            msg = record.msg

        level_name = fields['level_name']
        logger = fields['channel']
        timestamp = fields['time'].strftime('%Y-%m-%dT%H:%M:%S.%fZ')

        # Pop unnecessary or handled keys
        for key in ['level', 'level_name', 'heavy_initialized', 'information_pulled',
                    'msg', 'message', 'channel', 'time']:
            if key in fields:
                fields.pop(key)

        if 'exc_info' in fields:
            if fields['exc_info']:
                formatted = tb.format_exception(*fields['exc_info'])
                fields['exception'] = formatted
            fields.pop('exc_info')

        if 'exc_text' in fields and not fields['exc_text']:
            fields.pop('exc_text')

        logr = self.defaults.copy()

        logr.update(
            {'message'    : msg,
             'level'      : level_name,
             'logger'     : logger,
             '@timestamp' : timestamp,
             'source_host': self.source_host,
             'context'    : self._build_fields(logr, fields)
             }
        )

        if self.release:
            logr.update({'release': self.release})

        if self.enable_handler_fields:
            handler_fields = handler.__dict__.copy()
            # Delete useless fields (they hold object references)
            for delete_handler_field in ['stream', 'formatter', 'lock']:
                if delete_handler_field in handler_fields:
                    handler_fields.pop(delete_handler_field)
            logr.update({'@handler': handler_fields})

        return json.dumps(logr, default=self.json_default, cls=self.json_cls)
        # return ''

    @staticmethod
    def _build_fields(defaults, fields):
        """Return provided fields including any in defaults"""
        return dict(list(defaults.get('@fields', {}).items()) + list(fields.items()))
