import sys
from concurrent.futures.thread import ThreadPoolExecutor
from queue import Queue
from threading import Thread
import threading


def _handler(event_json, respond):
    pass


running = False

PY3K = sys.version_info >= (3, 0)

if PY3K:
    source = sys.stdin.buffer
else:
    # Python 2 on Windows opens sys.stdin in text mode, and
    # binary data that read from it becomes corrupted on \r\n
    if sys.platform == "win32":
        # set sys.stdin to binary mode
        import os, msvcrt

        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
    source = sys.stdin

BUFFER_SIZE = 1024


def read(byte_count):
    recv = source.read(min(byte_count, BUFFER_SIZE))
    l = len(recv)
    while l < byte_count:
        next_recv = source.readrecv(min(byte_count - l, BUFFER_SIZE))
        recv += next_recv
        l += len(next_recv)
    return recv


def set_handler(handler):
    global _handler
    _handler = handler


def print_err(*msgs):
    print(" ".join(str(msg) for msg in msgs), file=sys.stderr)
    pass


startup_latch = None
shutdown_latch = None
threaded_execution = "--threaded" in sys.argv


# print_err("threaded mode:", threaded_execution)


def stop(clear_message_queue=False):
    global running

    if threaded_execution:
        shutdown_latch.wait()
        if clear_message_queue:
            while not message_queue.empty():
                message_queue.get(False)
    running = False


def start():
    global running, startup_latch, shutdown_latch
    if running:
        return
    running = True
    if threaded_execution:
        startup_latch = CountDownLatch(2)
        shutdown_latch = CountDownLatch(2)
        Thread(target=message_reader).start()
        Thread(target=message_writer).start()
        startup_latch.wait()
    else:
        while running:
            mid, message = fetch_message()
            _handler(message, lambda response: send_message(mid, response))


def __handler(array_args):
    # print_err("__HANDLER CALLED", *array_args)
    result = None
    try:
        result = _handler(*array_args)
    except Exception as e:
        print_err("EXCEPTION OCCURRED")
        print_err(e)
    return result


def message_reader():
    startup_latch.count_down()
    try:
        while running:
            mid, event_json = fetch_message()
            # respond = lambda response: message_queue.put((mid, response))
            thread_pool.submit(__handler, [event_json, respond(mid)])
            # thread_pool.submit(__handler, [event_json, respond])
    except Exception as e:
        print_err(e)
    shutdown_latch.count_down()


def respond(mid):
    return lambda response: message_queue.put((mid, response))


def message_writer():
    startup_latch.count_down()
    while running:
        mid, message = message_queue.get()
        send_message(mid, message)
    shutdown_latch.count_down()


message_queue = Queue()
thread_pool = ThreadPoolExecutor()


def fetch_message():
    id = read_int_bytes()
    event_length = read_int()
    message = read_UTF(event_length)
    return id, message


def read_int():
    return parse_int(read_int_bytes())


def parse_int(bytes):
    return int.from_bytes(bytes, "big")


def read_int_bytes():
    return read(4)


def read_UTF(length):
    return read(length).decode("utf-8")


def send_message(mid, response):
    # print_err("> WRITING [" + str(mid) + "]: " + str(response))
    to_write = mid + int_to_bytes(len(response)) + response
    sys.stdout.buffer.write(to_write)
    sys.stdout.flush()


def int_to_bytes(n):
    return n.to_bytes(4, "big")


def bytes_to_int(bytes):
    return int.from_bytes(bytes, "big")


class CountDownLatch:
    def __init__(self, count=1):
        self.count = count
        self.lock = threading.Condition()

    def count_down(self):
        self.lock.acquire()
        self.count -= 1
        if self.count <= 0:
            self.lock.notifyAll()
        self.lock.release()

    def wait(self):
        self.lock.acquire()
        while self.count > 0:
            self.lock.wait()
        self.lock.release()
