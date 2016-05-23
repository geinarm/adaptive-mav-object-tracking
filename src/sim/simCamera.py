#!/usr/bin/env python2

""" Camera module.
"""

import socket
import sys
import numpy as np

import cv2
import debug
import math
import threading
import Queue


class Camera(threading.Thread):
    """ Encapsulates the camera on the AR Parrot Drone 2.0. Handles the
        receiving of images from the drone using OpenCV.
    """
    def __init__(self, debug_queue, error_queue, address, queue):
        threading.Thread.__init__(self)
        self.debug_queue = debug_queue
        self.error_queue = error_queue
        self.address = address
        self.queue = queue
        self.cap = False
        self.socket = None;

    def run(self):
        try:
            self.connect();
        except Exception as ex:
            print(ex)

        while True:
            #(ret, frame) = cap.read()
            data = self.socket.recv(10000)
            array = np.fromstring(data, dtype='uint8')
            img = cv2.imdecode(array, 1)

            try:
                self.queue.put(img, block=False)
            except Queue.Full:
                pass

    def connect(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        #server_address = (self.address[0], self.address[1])
        sock.connect(self.address)
        
        self.socket = sock


def _test_camera():
    """ Tests the camera module.
    """
    #pdb.set_trace()

    # Conduct tests...
    _test_get_image()
    #_test_get_windows(show_window=True)


def _test_get_image():
    # Set up debug.
    verbosity = 1
    error_queue = Queue.Queue()
    debug_queue = Queue.Queue()
    debugger = debug.Debug(verbosity, debug_queue, error_queue)

    # Make sure the images look right.
    image_queue = Queue.Queue(maxsize=1)
    
    #camera_address = 'tcp://192.168.1.1:5555'
    camera_address = 'tcp://127.0.0.1:5555'
    #camera_address = '../samples/test_people_walking.avi'
    #camera_address = 'dog'
    #camera_address = 0;
    
    camera = Camera(debug_queue, error_queue, camera_address, image_queue)
    camera.daemon = True
    camera.start()

    try:
        i = 0
        while True:
            debugger.debug()
            image = image_queue.get(block=True, timeout=10)
            cv2.imshow('image', image)
            key = cv2.waitKey(1) & 0xff
            if key == ord('q'):
                break
            elif key == ord('s'):
                cv2.imwrite('image_%s.png' % str(i), image)
                i += 1
        debugger.debug()
    except debug.Error as e:
        e.print_error()
    except KeyboardInterrupt:
        sys.exit(0)

    print('End loop');
    sys.exit(0)


if __name__ == '__main__':
    import pdb
    import sys
    _test_camera()
