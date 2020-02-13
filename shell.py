import sys

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


import gym
import json
import numpy as np

instanceCount = 0
instances = {}


def close(instance_id):
    get_env(instance_id).close()
    del instances[instance_id]


def handle(event):
    event_type = event.get("type")
    if event_type == "make":
        return make(event.get("envId"), event.get("render"))
    else:
        instance_id = event.get("id")
        if event_type == "step":
            return step(instance_id, event.get("action"))
        elif event_type == "reset":
            return reset(instance_id)
        elif event_type == "shape":
            return shape(instance_id)
        elif event_type == "close":
            close(instance_id)


def make(envId, render=False):
    global instanceCount
    id = instanceCount
    instances[id] = {
        "env": gym.make(envId),
        "render": render
    }
    instanceCount += 1
    return int_to_bytes(id)


def step(id, action):
    global reward, done, state
    instance = instances[id]
    env = instance.get("env")

    space_type = type(env.action_space)
    if space_type == gym.spaces.box.Box:
        state, reward, done, info = env.step(np.asarray(action, np.float))
    elif space_type == gym.spaces.discrete.Discrete:
        state, reward, done, info = env.step(action)

    state = format_state(state)
    result = {
        # "info": info,
        "reward": reward,
        "done": done,
        "observation": state
    }
    if instance.get("render"):
        env.render()

    return dict_to_utf_bytes(result)


def reset(id):
    state = get_env(id).reset()
    result = {"observation": format_state(state)}
    return dict_to_utf_bytes(result)


def shape(instance_id):
    response = {}
    env = get_env(instance_id)
    response["action"] = serialise_space(env.action_space)
    response["observation"] = serialise_space(env.observation_space)
    return dict_to_utf_bytes(response)


def dict_to_utf_bytes(dict):
    return bytes(json.dumps(dict), 'utf-8')


def int_to_bytes(n):
    return n.to_bytes(4, "big")


def get_env(id):
    return instances[id].get("env")


def format_state(state):
    if type(state).__module__ == np.__name__:
        state = state.flatten().tolist()

    # print(state)
    return state


def serialise_space(space):
    action_type = type(space)
    if action_type == gym.spaces.box.Box:
        return {
            "type": "box",
            "shape": space.shape,
            "high": space.high.tolist(),
            "low": space.low.tolist()
        }
    elif action_type == gym.spaces.discrete.Discrete:
        return {
            "type": "discrete",
            "size": space.n,
        }


def read_int():
    return parse_int(read_int_bytes())


def parse_int(bytes):
    return int.from_bytes(bytes, "big")


def read_int_bytes():
    return read(4)


def read_UTF(length):
    return read(length).decode("utf-8")


while True:
    mid_bytes = read_int_bytes()
    mid = parse_int(mid_bytes)
    in_length = read_int()
    event_string = read_UTF(in_length)
    event = json.loads(event_string)
    response = handle(event)

    # print("> MID:" + str(mid), file=sys.stderr)
    # print("> EVENT: " + event_string, file=sys.stderr)
    # print("> RESPONSE: " + str(response), file=sys.stderr)
    # sys.stderr.flush()
    # # TODO: IMPLEMENT THREAD(-POOL)ED HANDLING

    if response is not None:
        sys.stdout.buffer.write(mid_bytes)
        sys.stdout.buffer.write(int_to_bytes(len(response)))
        sys.stdout.buffer.write(response)
        sys.stdout.flush()
