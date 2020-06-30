import ctypes
import time
import sys
import re
import PySimpleGUIQt as sg
import sys
import threading
import socket
import traceback
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import PySide2

HOST = '127.0.0.1'  # Standard loopback interface address (localhost)
PORT = 65432        # Port to listen on (non-privileged ports are > 1023)

class TimerManager(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.timers = []
        self.mutex = threading.Lock()
        self.alive = True
        self.timer_expired = False

    def run(self):
        while self.alive:
            time.sleep(1)
            with self.mutex:
                for timer in self.timers:
                    timer['time'] -= 1
                    if timer['time'] <= 0:
                        ctypes.windll.user32.MessageBoxW(None, timer['reason'], u'Timer', 0x00001000 | 0x00000040)

                old_len = len(self.timers)
                self.timers = [t for t in self.timers if t['time'] > 0]
                if len(self.timers) < old_len:
                    self.timer_expired = True

    def kill(self):
        self.alive = False

    def set_timer(self, input):
        try:
            entry = input.split(' ')

            matches = re.match('([0-9]+)([sSmMhHdD]?)', entry[0])
            if matches:
                if matches[2]:
                    if matches[2].lower() == 's':
                        timer = int(matches[1])
                    elif matches[2].lower() == 'm':
                        timer = 60 * int(matches[1])
                    elif matches[2].lower() == 'h':
                        timer = 3600 * int(matches[1])
                    elif matches[2].lower() == 'd':
                        timer = 86400 * int(matches[1])
                    else:
                        raise Exception('Invalid time string')
                else:
                    timer = int(matches[1])
            else:
                raise Exception('Invalid time string')

            if len(entry) > 1:
                reason = u' '.join(entry[1:])
            else:
                reason = u'The timer has expired'

            with self.mutex:
                self.timers.append({'time': timer, 'reason': reason})
        except Exception as e:
            print('Exception: {}'.format(str(e)))

    def get_timers(self):
        with self.mutex:
            return self.timers

    def has_timer_expired(self):
        with self.mutex:
            return self.timer_expired

class TimerInterface:
    def __init__(self):
        sg.theme('DarkBlue3')

        self.window = None
        self.layout = None
        self.text = None
        self.table = None

        menu_def = ['BLANK', ['5', '10', '15', '20', '25', '30', '35', '40', '45', '50', '55', '60', 'Open', 'Exit']]  
        self.tray = sg.SystemTray(menu=menu_def, tooltip='test')

        self.timer_manager = TimerManager()

    def run(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as self.s:
                self.s.settimeout(0.01)
                self.s.bind((HOST, PORT))
                self.s.listen()
                self.timer_manager.start()
                self.process_events()
                self.timer_manager.kill()
        except Exception as e:
            print(traceback.format_exc())
            self.timer_manager.kill()

    def open_window(self):
        if not self.window:
            self.text = sg.InputText('')
            table_data, visible = self.get_table_data()
            self.table = sg.Table(table_data, headings=['Time(s)', 'Name'], visible=visible, col_widths=[10, 300])
            self.layout = [[self.text], [self.table]]
            self.window = sg.Window('Timers', self.layout, return_keyboard_events=True, size=(350, 30))
            print(self.table.Widget)
        else:
            self.window.UnHide()
            self.window.bring_to_front()

    def kill_window(self):
        if self.window:
            self.window.Close()
            self.window = None
            self.layout = None
            self.text = None

    def get_table_data(self):
        timers = []
        for timer in self.timer_manager.get_timers():
            timers.append([str(timer['time']), timer['reason']])
        return (timers if len(timers) > 0 else [['        ', '                                                                 ']]), len(timers) > 0

    def process_events(self):
        last_time = time.time()
        self.open_window()
        while True:
            try:
                conn, addr = self.s.accept()
                with conn:
                    d = conn.recv(64).decode()
                    if d == 'activate':
                        self.open_window()
            except Exception as e:
                pass

            if self.window:
                event, values = self.window.read(timeout=10)
                if event == 'special 16777220':
                    if values[0].lower() == 'exit':
                        break
                    input = values[0]
                    if(input[-1] == '-'):
                        input = input[:-1]
                        self.kill_window()
                    if input:
                        self.timer_manager.set_timer(input)
                    self.text.update(value='')
                    table_data, visible = self.get_table_data()
                    self.table.update(values=table_data, visible=visible)
                if not event:
                    self.kill_window()
                elif event != '__TIMEOUT__':
                    print(event)
                if time.time() >= last_time + 1:
                    table_data, visible = self.get_table_data()
                    self.table.update(values=table_data, visible=visible)
                    header = self.table.Widget.horizontalHeader()   
                    header.setSectionResizeMode(1, PySide2.QtWidgets.QHeaderView.ResizeToContents)
                    last_time = time.time()

            menu_item = self.tray.Read(timeout=10)
            if menu_item == 'Exit':  
                break
            elif menu_item == 'Open':  
                sg.Popup('Menu item chosen', menu_item)
            elif menu_item == '__ACTIVATED__':
                self.tray.update(tooltip='activated')
                self.open_window()
        self.kill_window()

if __name__ == '__main__':
    interface = TimerInterface()
    interface.run()
