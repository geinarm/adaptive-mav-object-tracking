#!/usr/bin/env python2.7

""" A tool that allows the user to fly the drone easily from a gui application.
"""

import argparse
import json
import sys
import socket
import threading
import urllib2

import cv2
import numpy as np
import Tkinter as tk
from PIL import ImageTk, Image

DEBUG = 0
try:
    import pdb
except ImportError:
    DEBUG = 0


class Error(Exception):
    """ Base exception for the module.
    """
    def __init__(self, msg):
        self.msg = 'Error: %s' % msg

    def print_error(self, msg):
        print(self.msg)


class ArgumentError(Error):
    def __init__(self, arg):
        self.msg = "Error: argument '%s' is invalid." % arg


class FlyArgs(object):
    """ Argument parser for flying tool.
    """
    def __init__(self):
        # Basic info.
        version = 1.0
        name = 'fly'
        date = '02/21/15'
        author = 'Igor Janjic'
        organ = 'Graduate Research at Virginia Tech'
        desc = 'A tool that allows the user to easily fly a Parrot AR Drone 2.0.'
        epil = 'Application %s version %s. Created by %s on %s for %s.' % (name, version, author, date, organ)

        # Arguments help.
        help_help = 'Show this help message and exit.'
        gui_help = 'Use this flag if you want to use the gui.'
        record_help = 'Use this argument if you want to record the front and bottom camera streams as mpeg. If so, pass the name of the files the streams will be saved in.'
        verb_help = 'Increase the output verbosity.'
        streams_help = 'Port of the image stream for the front and bottom camera seperated by a comma.'

        # Argparser.
        self.arg_parser = argparse.ArgumentParser(prog=name, description=desc, epilog=epil, add_help=False)
        required_args = self.arg_parser.add_argument_group('Required arguments', '')
        optional_args = self.arg_parser.add_argument_group('Optional arguments', '')

        optional_args.add_argument('-h', '--help', action='help', help=help_help)
        optional_args.add_argument('-g', '--gui', dest='gui', action='store_true', default=False, help=gui_help)
        optional_args.add_argument('-v', '--verbosity', dest='verb', action='count', default=0, help=verb_help)
        optional_args.add_argument('-r', '--record', type=str, dest='record', help=record_help, metavar='\b')
        required_args.add_argument('-s', '--streams', type=str, dest='streams', required=True, help=streams_help, metavar='\b')

    def parse(self):
        self.args = self.arg_parser.parse_args()

        # Parse the streams argument.
        self.streams = None
        if self.args.streams is not None:
            try:
                self.streams = self.args.streams.split(',')
                # Make sure the ports are real.
            except ValueError:
                raise ArgumentError(self.args.streams)

        # Parse the record argument.
        self.record = None
        if self.args.record is not None:
            try:
                self.record = self.args.record.split(',')
                # Make sure that the file can be accessed with correct permissions.
            except ValueError:
                raise ArgumentError(self.args.record)


class Fly(object):
    """ Flying tool.
    """
    def __init__(self, gui, verb, record, streams):
        self.verb = verb
        self.fc_port = streams[0] if streams else None
        self.bc_port = streams[1] if streams else None
        self.fc_filename = record[0] if record else None
        self.bc_filename = record[1] if record else None
        self.gui = self.create_gui() if gui else None
        self.speed = 0.3

        # Create the json template that will be passed to the cmd server.
        self.default_query = {
            'X': 0.0,
            'Y': 0.0,
            'C': 0.0,
            'T': False,
            'L': False,
            'S': False
        }

        self.net_thread = Network()
        self.net_thread.daemon = True
        self.net_thread.start()

    def create_gui(self):
        """ Factory method that builds the GUI and passes the fly object to it.
        """
        return Fly.FlyGUI(self)

    def start(self):
        """ Starts the flying tool.
        """
        if self.verb >= 0:
            print('Parrot AR 2 Flying Tool')
        if self.verb >= 1:
            if self.gui:
                print(':: GUI flag set.')
            print(':: Verbosity set to %d.' % self.verb)
            if self.fc_port and self.bc_port:
                print(':: Accessing front camera stream at port: %s.' % self.fc_port)
                print(':: Accessing bottom camera stream at port: %s.' % self.bc_port)
            if self.fc_filename and self.br_filename:
                print(':: Saving front camera stream to file: %s.' % self.fc_filename)
                print(':: Saving bottom camera stream to file: %s.' % self.br_filename)
            print(':: Default speed set to %0.1f' % self.speed)
            print
            print('Waiting for input...')
        if self.gui:
            self.gui.run()

    class FlyGUI(object):
        """ GUI for flying tool.
        """
        def __init__(self, fly):
            self.fly = fly
            self.root = tk.Tk()
            if self.root:
                self.root.resizable(0, 0)  # change this later
                self.root.wm_title("Parrot AR 2 Flying Tool")
                self.menu = tk.Menu(self.root)
                self.file_menu = tk.Menu(self.menu, tearoff=0)
                self.help_menu = tk.Menu(self.menu, tearoff=0)
                self.fc_frame = tk.Frame(self.root)
                self.bc_frame = tk.Frame(self.root)
                self.controls_frame = tk.Frame(self.root)
                self.info_frame = tk.Frame(self.root)

                self.root.config(menu=self.menu)
                self.create_gui()

        def run(self):
            self.update_video()
            self.root.mainloop()
            sys.exit(0)

        def create_gui(self):
            """ Creates the gui.
            """
            # Create the layout of the frames.
            self.fc_frame.pack()
            self.bc_frame.pack()
            self.controls_frame.pack()
            self.info_frame.pack()

            # Create the layout of the scale.
            self.control_speed = tk.Scale(self.controls_frame, from_=0, to=1, orient=tk.HORIZONTAL, resolution=0.1, command=self.callback_scale_speed)
            self.control_speed.set(0.3)
            self.control_speed.grid(row=3, column=0, columnspan=3)

            # Create the layout of the buttons.
            self.control_tl = tk.Button(self.controls_frame, text='TL', command=self.callback_button_tl)
            self.control_tr = tk.Button(self.controls_frame, text='TR', command=self.callback_button_tr)
            self.control_left = tk.Button(self.controls_frame, text='Left', command=self.callback_button_left)
            self.control_right = tk.Button(self.controls_frame, text='Right', command=self.callback_button_right)
            self.control_up = tk.Button(self.controls_frame, text='Up', command=self.callback_button_forward)
            self.control_down = tk.Button(self.controls_frame, text='Down', command=self.callback_button_backward)
            self.control_land = tk.Button(self.controls_frame, text='Land', command=self.callback_button_land)
            self.control_takeoff = tk.Button(self.controls_frame, text='Takeoff', command=self.callback_button_takeoff)
            self.control_stop = tk.Button(self.controls_frame, text='Stop', command=self.callback_button_stop)

            self.control_tl.grid(row=0, column=0, sticky=tk.S+tk.E+tk.W)
            self.control_up.grid(row=0, column=1, sticky=tk.S+tk.E+tk.W)
            self.control_tr.grid(row=0, column=2, sticky=tk.S+tk.E+tk.W)
            self.control_left.grid(row=1, column=0, sticky=tk.N+tk.S+tk.E+tk.W)
            self.control_down.grid(row=1, column=1, sticky=tk.N+tk.S+tk.E+tk.W)
            self.control_right.grid(row=1, column=2, sticky=tk.N+tk.S+tk.E+tk.W)
            self.control_land.grid(row=2, column=0, sticky=tk.N+tk.S+tk.E+tk.W)
            self.control_stop.grid(row=2, column=1, sticky=tk.N+tk.S+tk.E+tk.W)
            self.control_takeoff.grid(row=2, column=2, sticky=tk.N+tk.S+tk.E+tk.W)

            # Create the layout of the info labels.
            self.altitude = tk.Label(self.info_frame, text='Altitude:', anchor=tk.W, justify=tk.LEFT, width=90)
            self.position = tk.Label(self.info_frame, text='Position:', anchor=tk.W, justify=tk.LEFT, width=90)
            # self.altitude.pack(fill='x', expand=True)
            # self.position.pack(fill='x', expand=True)

            # # Create the layout of the menu bar.
            self.file_menu.add_command(label='Exit', command=self.root.quit)
            self.help_menu.add_command(label='Help', command=self.callback_help)
            self.help_menu.add_command(label='About', command=self.callback_about)

            self.menu.add_cascade(label='File', menu=self.file_menu)
            self.menu.add_cascade(label='Help', menu=self.help_menu)

            # Test images for frames.
            test_image = Image.open('../samples/test_cameras.jpg')
            test_photo = ImageTk.PhotoImage(test_image)
            self.fc_test_label = tk.Label(self.fc_frame, image=test_photo)
            self.fc_test_label.image = test_photo
            bc_test_label = tk.Label(self.bc_frame, image=test_photo)
            bc_test_label.image = test_photo

            # self.world_label.bind('<Configure>', self.resize)
            self.fc_test_label.pack()
            bc_test_label.pack()

        def callback_help(self):
            filewin = tk.Toplevel(self.root)
            help_text = 'Help'
            label = tk.Label(filewin, text=help_text)
            label.pack()
            pass

        def callback_about(self):
            pass

        def callback_scale_speed(self, value):
            self.fly.speed = float(value)

        def callback_button_tl(self):
            print('Sending command to turn left at speed %0.1f.' % self.fly.speed)
            query = self.fly.default_query.copy()
            query['C'] = -self.fly.speed
            query_json = json.dumps(query)
            self.fly.net_thread.send_query(query_json)

        def callback_button_tr(self):
            print('Sending command to turn right at speed %0.1f.' % self.fly.speed)
            query = self.fly.default_query.copy()
            query['C'] = self.fly.speed
            query_json = json.dumps(query)
            self.fly.net_thread.send_query(query_json)

        def callback_button_left(self):
            print('Sending command to fly left at speed %0.1f.' % self.fly.speed)
            query = self.fly.default_query.copy()
            query['X'] = -self.fly.speed
            query_json = json.dumps(query)
            self.fly.net_thread.send_query(query_json)

        def callback_button_right(self):
            print('Sending command to fly right at speed %0.1f.' % self.fly.speed)
            query = self.fly.default_query.copy()
            query['X'] = self.fly.speed
            query_json = json.dumps(query)
            self.fly.net_thread.send_query(query_json)

        def callback_button_forward(self):
            print('Sending command to fly forward at speed %0.1f.' % self.fly.speed)
            query = self.fly.default_query.copy()
            query['Y'] = self.fly.speed
            query_json = json.dumps(query)
            self.fly.net_thread.send_query(query_json)

        def callback_button_backward(self):
            print('Sending command to fly backward speed %0.1f.' % self.fly.speed)
            query = self.fly.default_query.copy()
            query['Y'] = -self.fly.speed
            query_json = json.dumps(query)
            self.fly.net_thread.send_query(query_json)

        def callback_button_land(self):
            print('Sending command to land.')
            query = self.fly.default_query.copy()
            query['L'] = True
            query_json = json.dumps(query)
            self.fly.net_thread.send_query(query_json)

        def callback_button_takeoff(self):
            print('Sending command to takeoff.')
            query = self.fly.default_query.copy()
            query['T'] = True
            query_json = json.dumps(query)
            self.fly.net_thread.send_query(query_json)

        def callback_button_stop(self):
            print('Sending command to stop.')
            query = self.fly.default_query.copy()
            query['S'] = True
            query_json = json.dumps(query)
            self.fly.net_thread.send_query(query_json)

        def update_video(self):
            self.root.after(30, self.update_video)
            frame = self.fly.net_thread.parrot_cam.get_frame()
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_frame = Image.fromarray(frame)
            pil_frame - pil_frame.resize((400, 400), Image.ANTIALIAS)
            photo_frame = ImageTk.PhotoImage(pil_frame)
            self.fc_test_label.config(image=photo_frame)
            self.fc_test_label.image = photo_frame


class Network(threading.Thread):
    """ Handles network stuff.
    """
    def __init__(self):
        threading.Thread.__init__(self)
        self.server_address = 'localhost'
        self.server_png_port = 9000
        self.server_cmd_port = 9001
        self.parrot_cam = ipCamera(url='http://192.168.1.2:9000')

    def run(self):
        print("Starting")

        # Connect to the node js servers.
        self.png_soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.cmd_soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # self.png_soc.connect((self.server_address, self.server_png_port))
        self.cmd_soc.connect((self.server_address, self.server_cmd_port))

    def send_query(self, query):
        self.cmd_soc.send(query)


class ipCamera(object):
    """
    """
    def __init__(self, url):
        self.url = url
        self.req = urllib2.Request(self.url)

    def get_frame(self):
        response = urllib2.urlopen(self.req)
        img_array = np.asarray(bytearray(response.read()), dtype=np.uint8)
        frame = cv2.imdecode(img_array, 1)
        return frame


def main():
    try:
        DEBUG = 0
        if DEBUG:
            pdb.set_trace()
        fa = FlyArgs()
        fa.parse()
        f = Fly(fa.args.gui, fa.args.verb, fa.record, fa.streams)
        f.start()
    except KeyboardInterrupt:
        # Close gui thread!
        print('\nClosing.')
        sys.exit(1)
    except ArgumentError as e:
        e.print_error()
        sys.exit(1)


if __name__ == '__main__':
    main()
