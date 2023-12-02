from enum import Enum, unique
from struct import calcsize, unpack_from, pack
from threading import Lock
from time import sleep
from typing import Optional, Dict, Union, List

import serial
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QMessageBox
from serial import Serial, SerialException
from serial.tools import list_ports
from serial.tools.list_ports_common import ListPortInfo

import numpy as np
from numpy import ndarray
from pyqtgraph import PlotDataItem, PlotWidget


@unique
class PacemakerState(Enum):
    NOT_CONNECTED = 1
    CONNECTED = 2
    REGISTERED = 3


# 负责接发数据
class _SerialHandler(QThread):
    _running: bool
    _buf: bytearray
    _conn: Serial
    _num_bytes_to_read: int
    _sent_data: bytes
    _send_params: bool
    _lock: Lock

    # A signal that's emitted every time we receive ECG data
    ecg_data_update: Signal = Signal(tuple, tuple)

    # A signal that's emitted upon param verification with the pacemaker
    params_received: Signal = Signal(bool, str)

    # https://docs.python.org/3.7/library/struct.html#format-strings
    _num_floats = 20
    _PARAMS_FMT_STR, _ECG_FMT_STR, _ECG_DATA_STR = "=3BfB2fBf4H5B", f"={_num_floats}f", f"={_num_floats // 2}f"
    _PARAMS_NUM_BYTES, _ECG_NUM_BYTES, _ECG_DATA = calcsize(_PARAMS_FMT_STR), calcsize(_ECG_FMT_STR), calcsize(
        _ECG_DATA_STR)
    _REQUEST_ECG = pack("=B33x", 0x55)  # 开头是unsigned char，后面33个pad byte
    _PARAMS_ORDER = ["Pacing Mode", "Lower Rate Limit", "Upper Rate Limit", "Atrial Amplitude", "Atrial Pulse Width",
                     "Atrial Sensitivity", "Ventricular Amplitude", "Ventricular Pulse Width",
                     "Ventricular Sensitivity", "VRP", "ARP", "PVARP", "Fixed AV Delay", "Maximum Sensor Rate",
                     "Reaction Time", "Response Factor", "Recovery Time", "Activity Threshold"]

    def __init__(self):
        super().__init__()
        print("Serial handler init")

        self._running = False
        self._buf = bytearray()
        self._conn = Serial(baudrate=115200, timeout=0)
        self._num_bytes_to_read = self._ECG_NUM_BYTES + 1
        self._sent_data = bytes()
        self._send_params = False
        self._lock = Lock()  # lock is used to prevent concurrent accessing/modification of variables

    # Gets called when the thread starts, overrides method in QThread
    def run(self):
        self._running = True

        while self._running:
            # Check if the serial connection with the pacemaker is open
            if self._conn.is_open:
                try:
                    with self._lock:
                        if self._send_params:  # if we want to send params
                            self._send_params = False
                            self._conn.write(self._sent_data)
                        else:
                            self._conn.write(self._REQUEST_ECG)

                    line = self._readline()  # read one packet of num_bytes_to_read size

                    control_byte = line[0]  # first byte
                    line = line[1:]  # the rest of them

                    # If we've received ECG data, elif we've received params data
                    if control_byte == 0:
                        a_data = unpack_from(self._ECG_DATA_STR, line, 0)
                        v_data = unpack_from(self._ECG_DATA_STR, line, self._ECG_DATA)

                        self.ecg_data_update.emit(a_data, v_data)
                    elif control_byte == 1:
                        self._verify_params(line)

                except Exception as e:
                    print(e)
                    pass
            elif self._conn.port:
                self._try_to_open_port()
            else:
                sleep(1)

    # Read the output stream of the pacemaker
    def _readline(self) -> bytearray:
        buf_len: int = len(self._buf)

        # If buffer already contains more than num_bytes_to_read bytes, remove and return the oldest ones from buffer
        if buf_len >= self._num_bytes_to_read:
            r = self._buf[:self._num_bytes_to_read]
            self._buf = self._buf[self._num_bytes_to_read:]
            return r

        # Read serial data and store in buffer until we have num bytes to read bytes, then remove and return those
        while self._running and self._conn.is_open:
            data: Optional[bytes] = self._conn.read(self._num_bytes_to_read)
            buf_len = len(self._buf)

            if buf_len >= self._num_bytes_to_read:
                r = self._buf[:self._num_bytes_to_read]
                self._buf = self._buf[self._num_bytes_to_read:] + data
                return r
            else:
                self._buf.extend(data)

    # Attempt to open serial port with pacemaker
    def _try_to_open_port(self) -> None:
        with self._lock:
            try:
                self._conn.open()
                print("opened port")
            except SerialException:
                pass

    # Verify that the params sent to the pacemaker are the ones received
    def _verify_params(self, received_params: bytes) -> None:
        if self._sent_data != bytes(received_params[:self._PARAMS_NUM_BYTES]):
            self.params_received.emit(False, "The received parameters were not the same as the sent ones!\nPlease "
                                             "restart the DCM/Pacemaker or try a different Pacemaker!")
            print("The received parameters were not the same as the sent ones!\nPlease "
                  "restart the DCM/Pacemaker or try a different Pacemaker!")
        else:
            self.params_received.emit(True, "Successfully sent parameters!")
            print("Successfully sent parameters!")

    # Stops the thread
    def stop(self) -> None:
        with self._lock:
            self._running = False
            self._conn.close()

    # Set the serial connection port to that of the pacemaker, and clear the buffer
    def start_serial_comm(self, port: str) -> None:
        print(f"opening serial port {port} with pacemaker")
        self._buf = bytearray()
        with self._lock:
            self._conn.port = port

    # Safely close the serial connection and clear the port
    def stop_serial_comm(self) -> None:
        with self._lock:
            self._conn.close()
            self._conn.port = None

    # Update the parameters to send to the pacemaker, and enable the send flag
    def send_params_to_pacemaker(self, params_to_send: Dict[str, Union[int, float]]) -> None:
        with self._lock:
            self._sent_data = pack(self._PARAMS_FMT_STR, *[params_to_send[key] for key in self._PARAMS_ORDER])
            self._send_params = True


class ConnectionHandler(QThread):
    _running: bool
    _device: ListPortInfo
    _devices: List[ListPortInfo]
    _old_devices: List[ListPortInfo]
    _first_serial_num: str
    _current_state: PacemakerState
    _prev_state: PacemakerState
    _wanted_state: PacemakerState
    serial: _SerialHandler

    # A signal that's emitted every time we change state
    connect_status_change = Signal(PacemakerState, str)  # the str is the serial_num and/or a msg

    def __init__(self):
        super().__init__()
        print("Connection handler init")

        self._running = False

        self._device = serial.tools.list_ports.comports()
        self._devices = self._old_devices = []

        self._first_serial_num = ""

        self._current_state = self._prev_state = self._wanted_state = PacemakerState.NOT_CONNECTED

        # Initialize and start the serial connection handler
        self.serial = _SerialHandler()
        self.serial.start()

    # Gets called when the thread starts, overrides method in QThread
    def run(self):
        self._running = True
        self.connect_status_change.emit(PacemakerState.NOT_CONNECTED, "")

        while self._running:
            self._update_state()
            sleep(0.01)

    # Stops the thread and stops the serial conn thread
    def stop(self) -> None:
        self._running = False
        self.serial.stop()

    # State machine for pacemaker connection state. It was implemented like this because it offers us many benefits
    # such as cleaner, easier to read code, ensuring that a pacemaker gets registered only once, handling multiple
    # pacemakers being plugged into the same computer, and handling the New Patient btn presses in a much simpler way.
    def _update_state(self) -> None:
        # Get list of connected COM port devices
        self._devices = self._filter_devices(list_ports.comports())

        added = [dev for dev in self._devices if dev not in self._old_devices]  # difference between new and old
        removed = [dev for dev in self._old_devices if dev not in self._devices]  # difference between old and new

        # Update the current state if its not aligned with the state we want to be in
        if self._current_state != self._wanted_state:
            self._current_state = self._wanted_state

        # We're not connected to any pacemaker
        if self._current_state == PacemakerState.NOT_CONNECTED:
            if len(added) > 0:  # if there is a new device added
                self._device = added[0]

                if self._first_serial_num == "":  # if this is the first device connected, auto-register
                    self._first_serial_num = self._device.serial_number
                    self._wanted_state = PacemakerState.REGISTERED
                elif self._first_serial_num == self._device.serial_number:  # if the first device was replugged in
                    self._wanted_state = PacemakerState.REGISTERED
                else:  # another device is plugged in
                    self._wanted_state = PacemakerState.CONNECTED

        # We're connected to an unregistered pacemaker
        elif self._current_state == PacemakerState.CONNECTED:
            # The only way to go from CONNECTED to REGISTERED is if the New Patient btn is pressed
            if self._prev_state == PacemakerState.NOT_CONNECTED:
                self.connect_status_change.emit(PacemakerState.CONNECTED, f"{self._device.serial_number}, press New "
                                                                          f"Patient to register")
            # Handle a device being removed
            self._handle_removed_device(removed)

        # We're connected to a registered pacemaker
        elif self._current_state == PacemakerState.REGISTERED:
            # If we've just transitioned to REGISTERED, open the serial communication link
            if self._prev_state == PacemakerState.NOT_CONNECTED or self._prev_state == PacemakerState.CONNECTED:
                self.serial.start_serial_comm(self._device.device)
                self.connect_status_change.emit(PacemakerState.REGISTERED, self._device.serial_number)

            # Handle a device being removed
            self._handle_removed_device(removed)

        # Update variables that store previous cycle information
        self._old_devices = self._devices
        self._prev_state = self._current_state

    # Called when the New Patient button is pressed
    def register_device(self) -> None:
        if self._current_state == PacemakerState.CONNECTED:
            self._wanted_state = PacemakerState.REGISTERED
        elif self._device.serial_number:  # at this point, we've already registered the device
            self._show_alert("Already registered this pacemaker!")
        elif len(self._devices) > 0:  # we only connect to 1 device at a time, so the rest are ignored
            self._show_alert("Please unplug and replug the pacemaker you want to connect to!")
        else:
            self._show_alert("Please plug in a pacemaker!")

    # Handles the transition to NOT_CONNECTED if the pacemaker we're connected to is unplugged
    def _handle_removed_device(self, removed: List[ListPortInfo]) -> None:
        if any(self._device.serial_number == dev.serial_number for dev in removed):
            self._wanted_state = PacemakerState.NOT_CONNECTED
            self.connect_status_change.emit(PacemakerState.NOT_CONNECTED, removed[0].serial_number)
            self._device = ListPortInfo()
            self.serial.stop_serial_comm()

    # Called when the Pace Now button is pressed
    def send_data_to_pacemaker(self, params: Dict[str, Union[int, float]]) -> None:
        self.serial.send_params_to_pacemaker(params)  # 直接发送数据到pacemaker
        # if self._current_state == PacemakerState.REGISTERED:
        #     self.serial.send_params_to_pacemaker(params)
        # elif self._current_state == PacemakerState.CONNECTED:
        #     self._show_alert("Please register the pacemaker first!")
        # else:
        #     self._show_alert("Please plug in a pacemaker!")

    @staticmethod
    def _show_alert(msg: str) -> None:
        """
        Displays an information message with the specified text

        :param msg: the text to show
        """
        qm = QMessageBox()
        QMessageBox.information(qm, "Connection", msg, QMessageBox.Ok, QMessageBox.Ok)

    @staticmethod
    def _filter_devices(data: List[ListPortInfo]) -> List[ListPortInfo]:
        """
        Filter plugged in COM port devices so that we only connect to pacemaker devices
        The SEGGER devices have a Vendor ID of 0x1366 and Product ID of 0x1015

        :param data: list of all plugged in COM port devices
        :return: list of all plugged in pacemaker devices
        """
        return [dev for dev in data if dev.vid == 0x1366 and dev.pid == 0x1015]


class GraphsHandler:
    _atri_data: ndarray
    _vent_data: ndarray
    _atri_plot: PlotDataItem
    _vent_plot: PlotDataItem

    def __init__(self, atri_plot: PlotWidget, vent_plot: PlotWidget, data_size: int):
        print("Graphs handler init")

        # noinspection PyArgumentList
        atri_plot.setRange(xRange=[-1, data_size], yRange=[-0.5, 5.5], padding=0)
        atri_plot.setLimits(xMin=-1, xMax=data_size, maxXRange=data_size + 1, yMin=-0.5, yMax=5.5)
        atri_plot.setMouseEnabled(x=True, y=False)
        atri_plot.enableAutoRange(x=False, y=True)
        atri_plot.setAutoVisible(x=False, y=True)
        atri_plot.showGrid(x=True, y=True)
        atri_plot.hideButtons()
        atri_plot.setMenuEnabled(False)
        atri_plot.setLabel('left', "Amplitude", units='V', **{'color': '#FFF', 'font-size': '10pt'})
        atri_plot.setLabel('bottom', "Time", units='s', **{'color': '#FFF', 'font-size': '10pt'})
        atri_plot.getAxis('bottom').setHeight(30)
        # noinspection PyArgumentList
        vent_plot.setRange(xRange=[-1, data_size], yRange=[-0.5, 5.5], padding=0)
        vent_plot.setLimits(xMin=-1, xMax=data_size, maxXRange=data_size + 1, yMin=-0.5, yMax=5.5)
        vent_plot.setMouseEnabled(x=True, y=False)
        vent_plot.enableAutoRange(x=False, y=True)
        vent_plot.setAutoVisible(x=False, y=True)
        vent_plot.showGrid(x=True, y=True)
        vent_plot.hideButtons()
        vent_plot.setMenuEnabled(False)
        vent_plot.setLabel('left', "Amplitude", units='V', **{'color': '#FFF', 'font-size': '10pt'})
        vent_plot.setLabel('bottom', "Time", units='s', **{'color': '#FFF', 'font-size': '10pt'})
        vent_plot.getAxis('bottom').setHeight(30)

        # Initialize graphs to 0
        self._atri_data = np.zeros(data_size)
        self._vent_data = np.zeros(data_size)

        # Create new sense plots for the atrial and ventricular graphs, in blue
        self._atri_plot = atri_plot.plot(pen=(0, 229, 255))
        self._vent_plot = vent_plot.plot(pen=(0, 229, 255))

        self._plot_data()

    # Plot the sense data on the graphs
    def _plot_data(self) -> None:
        self._atri_plot.setData(self._atri_data)
        self._vent_plot.setData(self._vent_data)

    # Update and plot new received data
    def update_data(self, atri_data: tuple, vent_data: tuple):
        print('atri update:' + str(atri_data))
        size = len(atri_data)
        self._atri_data[:-size] = self._atri_data[size:]
        self._atri_data[-size:] = atri_data

        size = len(vent_data)
        print('vent update:' + str(vent_data))
        self._vent_data[:-size] = self._vent_data[size:]
        self._vent_data[-size:] = vent_data

        self._plot_data()

    # Show/hide the atrial data on the graphs
    def atri_vis(self, show: bool) -> None:
        self._atri_plot.show() if show else self._atri_plot.hide()

    # Show/hide the ventricular data on the graphs
    def vent_vis(self, show: bool) -> None:
        self._vent_plot.show() if show else self._vent_plot.hide()
