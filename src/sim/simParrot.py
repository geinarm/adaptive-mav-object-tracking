
""" Parrot module.

    Allows access to the drone's front and bottom cameras, the ability to
    send commands, and the ability to read the drone's navigation data.
"""

import cv2
import json
import Queue
import numpy as np

# Local modules.
#import remote
import simCamera as camera
import simController as controller
import debug
import simReceiver as receiver

# Tracking modules.
from tracking import bounding_box
from tracking import cam_shift

from ssclient import SSClient
from ssclient.messages import Vector3Msg

class Parrot(object):
    """ Encapsulates the AR Parrot Drone 2.0.

        Allows access to the drone's front and bottom cameras, the ability to
        send commands, and the ability to read the drone's navigation data.
    """

    TOPIC_JOYSTICK = '/dagger/joystick'
    TOPIC_CMD = '/dagger/cmd'
    TOPIC_FRONT_CAMERA = '/dagger/camera'
    TOPIC_NAV_DATA = '/dagger/nav'

    def __init__(self):

        self.latest_nav = None
        self.latest_cmd = None

        # The default command that is sent to the drone.
        self.default_cmd = {
            'X': 0.0,
            'Y': 0.0,
            'Z': 0.0,
            'R': 0.0,
            'C': 0,
            'T': False,
            'L': False,
            'S': False
        }        

        try:
            self.client = SSClient('localhost', 5557)
            self.client.subscribe(self.TOPIC_JOYSTICK, self.on_joystick)
            self.client.subscribe(self.TOPIC_FRONT_CAMERA, self.on_frame)
            self.client.subscribe(self.TOPIC_NAV_DATA, self.on_nav)
        except Exception as ex:
            print(ex)

        print('SimParrot connected')

        self.image_queue = Queue.Queue(maxsize=1)

    def get_navdata(self):
        return self.latest_nav

    def get_image(self):
        image = self.image_queue.get(block=True)
        return image

    def get_cmd(self):
        return self.latest_cmd


    def send_cmd(self, cmd):
        if(cmd):
            x = cmd['Y']
            y = cmd['X']
            z = cmd['Z']
            msg = Vector3Msg(x, y, -z)
            self.client.publish(msg, self.TOPIC_CMD)


    def exit(self):
        print('Drone exit')


    def on_joystick(self, joy):
        #print("joy")
        self.latest_cmd = {
            'X': joy.getRightX(),
            'Y': joy.getRightY(),
            'Z': joy.getLeftY(),
            'R': joy.getLeftX(),
            'C': 0,
            'T': joy.getButtonA(),
            'L': joy.getButtonB(),
            'S': joy.getButtonX(),
            'A': joy.getButtonY()
        }


    def on_frame(self, data):
        #print("Frame")
        array = np.fromstring(data.getBytes(), dtype='uint8')
        img = cv2.imdecode(array, 1)

        try:
            self.image_queue.put(img, block=False)
        except Queue.Full:
            pass
        except Exception as ex:
            print(ex)


    def on_nav(self, nav):
        #print("Nav")
        altitude = nav.getAltitude()
        roll = nav.getRoll()
        pitch = nav.getPitch()
        yaw = nav.getYaw()

        self.latest_nav = {'demo' : {'altitude':altitude, 'rotation': {'roll':roll, 'pitch':pitch, 'yaw':yaw } } }