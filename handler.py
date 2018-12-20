"""
uses a lot of code from logbook.queues.RedisHandler
"""
import collections
import socket
import threading

from logbook import Handler, NOTSET

from .formatter import LogstashFormatter

# OSError includes ConnectionError, ConnectionError includes ConnectionResetError
NETWORK_ERRORS = OSError


class LogstashHandler(Handler):
    """A handler that sends log messages to a Logstash instance through TCP.

    It publishes each record as json dump.

    To receive such records you need to have a running instance of Logstash.

    Example setup::

        handler = LogstashHandler('127.0.0.1', port='8888')
    """

    def __init__(self, host, port,
                 flush_threshold=1,
                 level=NOTSET,
                 filter=lambda r, h: r.level >= 11,
                 bubble=True,
                 flush_time=5,
                 queue_max_len=1000,
                 logger=None,
                 release=None):
        Handler.__init__(self, level, filter, bubble)

        self.address = (host, port)
        self.flush_threshold = flush_threshold
        self.queue = collections.deque(maxlen=queue_max_len)
        self.logger = logger

        self.formatter = LogstashFormatter(release=release)

        if logger:
            logger.info('Logstash log handler connects to {}:{}'.format(host, port))

        try:
            self._establish_socket()
        except NETWORK_ERRORS:
            if self.logger:
                self.logger.error('Logstash TCP port connection refused when initializing handler, maybe later')

        # Set up a thread that flushes the queue every specified seconds
        self._stop_event = threading.Event()
        self._flushing_t = threading.Thread(target=self._flush_task,
                                            args=(flush_time,))

        # set daemon to True may cause some messages not be sent when exiting, so I commented this out.
        # self._flushing_t.daemon = True
        self._flushing_t.start()

    def _establish_socket(self):
        self.cli_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.cli_sock.settimeout(5)
        self.cli_sock.connect(self.address)

    def _flush_task(self, duration):
        """Calls the method _flush_buffer every certain time.
        """
        while not self._stop_event.isSet():
            self._flush_buffer()
            self._stop_event.wait(duration)

    def _flush_buffer(self):
        """Flushes the messaging queue into Logstash.
        """
        # self.logger.debug(
        #    '[Flush task] {} flushing buffer, q length: {}'.format(threading.currentThread().name, len(self.queue)))
        while len(self.queue) > 0:
            item = self.queue.popleft()
            try:
                self.cli_sock.sendall((item + '\n').encode("utf8"))
            except NETWORK_ERRORS:
                try:
                    self.logger.warn("Network error when sending logs to Logstash, try re-establish connection")
                    self._establish_socket()
                    self.cli_sock.sendall((item + '\n').encode("utf8"))
                except NETWORK_ERRORS:
                    # got network error when trying to reconnect, put the item back to queue and exit
                    self.logger.error("Network error when re-establishing socket, message queued for next flush")
                    self.queue.appendleft(item)

    def disable_buffering(self):
        """Disables buffering.

        If called, every single message will be directly pushed to Logstash.
        """
        self._stop_event.set()
        self.flush_threshold = 1

    def emit(self, record):
        """Emits a JSON to Logstash.

        We have to check the length of queue before appending. Otherwise, when a bounded length deque is full and
        new items are added, a corresponding number of items are discarded from the opposite end. This is not what
        we want.
        """
        if len(self.queue) < self.queue.maxlen:
            self.queue.append(self.format(record))
        #    if len(self.queue) == self.flush_threshold:
        #       self._flush_buffer()
