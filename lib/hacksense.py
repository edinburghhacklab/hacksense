# -*- python -*-

import Queue
import atexit
import json
import logging
import logging.handlers
import os
import pika
import redis
import socket
import sys
import threading
import time
import traceback

__all__ = ["amqp_host", "amqp_exchange", "get_amqp_channel"]

amqp_host = "amqp.hacklab"
amqp_exchange = "events"

redis_host = "hacksense-redis.hacklab"
redis_channel = "hacksense"

try:
    filename = os.path.join(os.path.dirname(__file__), 'config.json')
    config = json.load(open(filename, 'r'))
except IOError, e:
    print 'Could not load config from %s: %r' % (filename, e)
    config = {}

def setup_logging(stderr_level=logging.INFO,
                  syslog_level=logging.INFO,
                  facility=logging.handlers.SysLogHandler.LOG_USER,
                  ident=os.path.basename(sys.argv[0]),
                  redirect=False):

    logger = logging.getLogger()
    logger.setLevel(min(stderr_level, syslog_level))

    stream_format_string = ident + ": %(message)s"
    stream_handler = logging.StreamHandler(stream=sys.__stderr__)
    stream_handler.setFormatter(logging.Formatter(fmt=stream_format_string))
    stream_handler.setLevel(stderr_level)
    #logger.addHandler(stream_handler)

    syslog_format_string = ident + "[%(process)s]: %(message)s"
    syslog_handler = logging.handlers.SysLogHandler(address="/dev/log", facility=facility)
    syslog_handler.log_format_string = "<%d>%s"
    syslog_handler.setFormatter(logging.Formatter(fmt=syslog_format_string))
    syslog_handler.setLevel(syslog_level)
    logger.addHandler(syslog_handler)
    
    if redirect:
        class Stdout(object):
            def write(self, data):
                if data.rstrip() != '':
                    logging.info("STDOUT: %s" % (data.rstrip()))
        class Stderr(object):
            def write(self, data):
                if data.rstrip() != '':
                    logging.warning("STDERR: %s" % (data.rstrip()))
        sys.stdout = Stdout()
        sys.stderr = Stderr()
        
    def exithandler():
        logging.info("Exiting")
    atexit.register(exithandler)

class AMQPTopic(object):
    def __init__(self):
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=amqp_host))
        self.channel = self.connection.channel()
        self.channel.exchange_declare(exchange=amqp_exchange, type="topic")
        
    def publish(self, topic, headers={}, body=""):
        new_headers = headers.copy()
        new_headers['src_hostname'] = socket.getfqdn()
        new_headers['src_script'] = sys.argv[0]
        new_headers['src_uid'] = os.getuid()
        new_headers['src_pid'] = os.getpid()
        self.channel.basic_publish(exchange=amqp_exchange,
                                   routing_key=topic,
                                   body=body,
                                   properties=pika.BasicProperties(
                                     timestamp=time.time(),
                                     headers=new_headers
                                   ))

    def subscribe_callback(self, topic, callback):
        result = self.channel.queue_declare(exclusive=True)
        queue_name = result.method.queue

        self.channel.queue_bind(exchange=amqp_exchange, queue=queue_name, routing_key=topic)
        
        self.channel.basic_consume(callback,
                                   queue=queue_name,
                                   no_ack=True)
        self.channel.start_consuming()

class RedisConnection(object):
    def __init__(self):
        self.redis = redis.StrictRedis(host=redis_host)
        self.channel = redis_channel
    def subscribe(self):
        ps = self.redis.pubsub()
        ps.subscribe(self.channel)
        for message in ps.listen():
            if message['type'] == 'message':
                yield json.loads(message['data'])
    def publish(self, topic, message):
        message2 = message.copy()
        message2['src_hostname'] = socket.getfqdn()
        message2['src_script'] = sys.argv[0]
        message2['src_uid'] = os.getuid()
        message2['src_pid'] = os.getpid()
        message2['topic'] = topic
        if not message2.has_key('timestamp'):
            message2['timestamp'] = time.time()
        self.redis.publish(self.channel)

class ThreadedRedisConnection(object):
    class Publisher(threading.Thread):
        def run(self):
            while True:
                msg = self.queue.get()
                self.redis.publish(self.channel, json.dumps(msg))
    class Subscriber(threading.Thread):
        def run(self):
            ps = self.redis.pubsub()
            ps.subscribe(self.channel)
            for message in ps.listen():
                if message['type'] == 'message':
                    self.queue.put(json.loads(message['data']))
    def __init__(self):
        self.redis = redis.StrictRedis(host=redis_host)
        self.channel = redis_channel
        self.subscriber = None
        self.publisher = None
    def publish(self, topic, message):
        if not self.publisher:
            logging.info("Creating publisher thread")
            self.publisher = self.Publisher()
            self.publisher.redis = self.redis
            self.publisher.channel = self.channel
            self.publisher.queue = Queue.Queue()
            self.publisher.daemon = True
            self.publisher.start()
        message2 = message.copy()
        message2['src_hostname'] = socket.getfqdn()
        message2['src_script'] = sys.argv[0]
        message2['src_uid'] = os.getuid()
        message2['src_pid'] = os.getpid()
        message2['topic'] = topic
        if not message2.has_key('timestamp'):
            message2['timestamp'] = time.time()
        self.publisher.queue.put(message2)
    def subscribe(self, timeout=None):
        if not self.subscriber:
            logging.info("Creating subscriber thread")
            self.subscriber = self.Subscriber()
            self.subscriber.redis = self.redis
            self.subscriber.channel = self.channel
            self.subscriber.queue = Queue.Queue()
            self.subscriber.daemon = True
            self.subscriber.start()
        while True:
            try:
                yield self.subscriber.queue.get(block=True, timeout=timeout)
            except Queue.Empty:
                yield None
