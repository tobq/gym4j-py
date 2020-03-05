import json
import porter
import gym
import numpy as np

instanceCount = 0
instances = {}


def handle(event_json, respond):
    event = json.loads(event_json)
    event_type = event.get("type")

    if event_type == "make":
        response = make(event.get("envId"), event.get("render"))
    else:
        instance_id = event.get("id")
        if event_type == "step":
            response = step(instance_id, event.get("action"))
        elif event_type == "reset":
            response = reset(instance_id)
        elif event_type == "shape":
            response = shape(instance_id)
        else:
            if event_type == "close":
                close(instance_id)
                response = b"{}"
            else:
                response = b"{}"
            # return

    respond(response)


def make(envId, render=False):
    global instanceCount
    id = instanceCount
    make = gym.make(envId)
    instances[id] = {
        "env": make,
        "render": render
    }
    instanceCount += 1
    return porter.int_to_bytes(id)


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


def close(instance_id):
    get_env(instance_id).close()
    del instances[instance_id]


def dict_to_utf_bytes(dict):
    return bytes(json.dumps(dict), 'utf-8')


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
            "high": space.high.flatten().tolist(),
            "low": space.low.flatten().tolist()
        }
    elif action_type == gym.spaces.discrete.Discrete:
        return {
            "type": "discrete",
            "size": space.n,
        }


porter.set_handler(handle)
porter.start()
