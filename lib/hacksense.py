# -*- python -*-

import os
import pika
import socket
import sys
import time

__all__ = ["amqp_host", "amqp_exchange", "get_amqp_channel"]

amqp_host = "amqp.hacklab"
amqp_exchange = "events"

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
