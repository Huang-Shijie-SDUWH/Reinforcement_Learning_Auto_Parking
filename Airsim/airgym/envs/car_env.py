import setup_path
import airsim
import numpy as np
import math
import time
# import datetime

import gym
from gym import spaces
from airgym.envs.airsim_env import AirSimEnv

class AirSimCarEnv(AirSimEnv):
    def __init__(self, ip_address):
        super().__init__()

        self.observation_space = spaces.Dict({
            'position': spaces.Box(low=-30, high=30, shape=(2,), dtype=np.float32),
            'orientation': spaces.Box(low=-math.pi, high=math.pi, shape=(1,), dtype=np.float32)
        })

        self.start_ts = 0

        self.state = {
            "position": np.zeros(3),
            "prev_position": np.zeros(3),
            "pose": None,
            "prev_pose": None,
            "collision": False,
        }

        self.car = airsim.CarClient(ip=ip_address)
        self.action_space = spaces.Discrete(11)

        self.car_controls = airsim.CarControls()
        self.car_state = None
        self.episode_time_count = 0

    def _setup_car(self):
        self.car.reset()
        self.car.enableApiControl(True)
        self.car.armDisarm(True)
        time.sleep(0.01)

    def __del__(self):
        self.car.reset()
        
    def _do_action(self, action):
        self.car_controls.brake = 0
        self.car_controls.throttle = -0.5
        self.car_controls.is_manual_gear = True
        self.car_controls.manual_gear = -1
        self.car_controls.steering = 0
        if action == 0:
            self.car_controls.throttle = 0
            self.car_controls.brake = 1
        elif action == 1:
            self.car_controls.steering = 0
        elif action == 2:
            self.car_controls.steering = 0.5
        elif action == 3:
            self.car_controls.steering = -0.5
        elif action == 4:
            self.car_controls.steering = 0.25
        elif action == 5:
            self.car_controls.steering = -0.25
        elif action == 6:
            self.car_controls.manual_gear = 1
            self.car_controls.throttle = 0.5
            self.car_controls.steering = 0
        elif action == 7:
            self.car_controls.manual_gear = 1
            self.car_controls.throttle = 0.5
            self.car_controls.steering = 0.5
        elif action == 8:
            self.car_controls.manual_gear = 1
            self.car_controls.throttle = 0.5
            self.car_controls.steering = -0.5
        elif action == 9:
            self.car_controls.manual_gear = 1
            self.car_controls.throttle = 0.5
            self.car_controls.steering = 0.25
        else:
            self.car_controls.manual_gear = 1
            self.car_controls.throttle = 0.5
            self.car_controls.steering = -0.25

        self.car.setCarControls(self.car_controls)
        self.episode_time_count += 1
        time.sleep(1)

    def _get_obs(self):
        self.car_state = self.car.getCarState()

        self.state["prev_pose"] = self.state["pose"]
        self.state["pose"] = self.car_state.kinematics_estimated
        self.state["collision"] = self.car.simGetCollisionInfo().has_collided
        obs_dict = {
            "position": (self.state["pose"].position.to_numpy_array()[0], self.state["pose"].position.to_numpy_array()[1]),
            "orientation": airsim.to_eularian_angles(self.state["pose"].orientation)[2]
        }
        return obs_dict # Image

    def _compute_reward(self):
        # MAX_SPEED = 0
        # MIN_SPEED = -10
        BETA = 0.9
        ALPHA = 1
        # positon(11.262, -17.765, 0.251) orientation(0, 0, -1, 0)

        # best_or = np.array([0, 0, -1, 0])
        best_pt = np.array([7.306, 11.489, 0.140])
        car_pt = self.state["pose"].position.to_numpy_array()
        # car_or = self.state["pose"].orientation.to_numpy_array()
        eula = airsim.to_eularian_angles(self.state["pose"].orientation)[2]
        reward = 0
        reward_dist = 0
        reward_orit = 0
        dist = 0
        reward_steering = 0
        if car_pt[0] < -7 or car_pt[0] > 10 or car_pt[1] < -8 or car_pt[1] > 24:
            reward = -100
        else:
            dist = 0.05 * (car_pt[0]-best_pt[0]) * (car_pt[0]-best_pt[0]) + 0.04 * (car_pt[1]-best_pt[1]) * (car_pt[1]-best_pt[1])
            reward_dist = 200 * math.exp(- BETA * dist)
            reward_orit = 150 * math.exp(- ALPHA * min(math.pi - eula, math.pi + eula))
            reward_steering = - 5 * self.car_controls.steering * self.car_controls.steering

            reward = reward_dist + reward_orit + reward_steering

        done = 0
        if reward < -0.5:
            done = 1
        if self.state["collision"] or self.episode_time_count > 30:
            reward = -100
            done = 1
        if done == 0 and np.linalg.norm(car_pt-best_pt) < 1.5 and (eula > 2.85 or eula < -2.85) and abs(self.car_state.speed) < 0.1:
            # done = 1
            reward = reward + 100
            print("Success!")
        print("speed",self.car_state.speed,"position",reward_dist,"orientation",reward_orit)
        print("reward",reward)
        return reward, done

    def step(self, action):
        self._do_action(action)
        obs = self._get_obs()
        reward, done = self._compute_reward()

        return obs, reward, done, self.state

    def reset(self):
        self._setup_car()
        # self._do_action(1)
        self.episode_time_count = 0
        return self._get_obs()
