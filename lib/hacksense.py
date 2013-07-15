# -*- python -*-

import atexit
import hashlib
import hmac
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

__all__ = ["amqp_host", "amqp_exchange", "get_amqp_channel"]

amqp_host = "amqp.hacklab"
amqp_exchange = "events"

redis_host = "hacksense-redis.hacklab"

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
        self.reconnect()

    def reconnect(self):
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=amqp_host, heartbeat_interval=30))
        self.channel = self.connection.channel()
        self.channel.exchange_declare(exchange=amqp_exchange, type="topic")        

    def digest(self, key, timestamp, topic, headers, body):
        h = hmac.HMAC(key, digestmod=hashlib.sha512)
        text = ""
        text += "%d:" % (timestamp)
        text += "%s:" % (topic)
        for k in sorted(headers.keys()):
            if k != "signature":
                text += "%s=%s:" % (k, headers[k])
        text += "%s" % (body)
        logging.debug("text: %s" % (text))
        h.update(text)
        return h.hexdigest()

    def publish(self, topic, headers={}, body="", retry=False, key=None):
        new_headers = headers.copy()
        new_headers['src_hostname'] = socket.getfqdn()
        new_headers['src_script'] = sys.argv[0]
        new_headers['src_uid'] = os.getuid()
        new_headers['src_pid'] = os.getpid()
        timestamp = time.time()
        if key:
            signature = self.digest(key, timestamp, topic, new_headers, body)
            new_headers['signature'] = signature
        if retry:
            delay = 1
            max_delay = 60
            while True:
                try:
                    self.channel.basic_publish(exchange=amqp_exchange,
                                               routing_key=topic,
                                               body=body,
                                               properties=pika.BasicProperties(
                                                   timestamp=timestamp,
                                                   headers=new_headers
                                                   ))
                    return
                except Exception, e:
                    logging.exception("Publish failed (will retry in %ds)" % (delay))
                    time.sleep(delay)
                    delay = min(delay*2, max_delay)
                    self.reconnect()
        else:
            self.channel.basic_publish(exchange=amqp_exchange,
                                       routing_key=topic,
                                       body=body,
                                       properties=pika.BasicProperties(
                                           timestamp=timestamp,
                                           headers=new_headers
                                           ))

    def subscribe_callback(self, topic, callback):
        result = self.channel.queue_declare(exclusive=True)
        queue_name = result.method.queue

        if type(topic) is list:
            for t in topic:
                self.channel.queue_bind(exchange=amqp_exchange, queue=queue_name, routing_key=t)
        else:
            self.channel.queue_bind(exchange=amqp_exchange, queue=queue_name, routing_key=topic)
        
        self.channel.basic_consume(callback,
                                   queue=queue_name,
                                   no_ack=True)
        self.channel.start_consuming()

class RedisConnection(object):
    def __init__(self):
        self.redis = redis.StrictRedis(host=redis_host)
