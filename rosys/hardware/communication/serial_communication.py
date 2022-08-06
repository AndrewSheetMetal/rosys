import logging
import os
from typing import Optional

import rosys
import serial
from nicegui import ui

from .communication import Communication

log = logging.getLogger('rosys.hardware.serial_communication')


class SerialCommunication(Communication):
    baudrate: int = 115200
    log_io: bool = False

    def __init__(self) -> None:
        super().__init__()
        self.device_path = SerialCommunication.get_device_path()
        if self.device_path is None:
            raise Exception('No serial port found')
        self.log.debug(f'connecting serial on {self.device_path} with baudrate {self.baudrate}')
        self.serial = serial.Serial(self.device_path, self.baudrate)
        self.buffer = ''

    @classmethod
    def is_possible(cls) -> bool:
        return cls.get_device_path() is not None

    @classmethod
    def get_device_path(cls) -> Optional[str]:
        device_paths = [
            '/dev/ttyTHS1',
            '/dev/ttyUSB0',
            '/dev/tty.SLAB_USBtoUART',
            '/dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0',
            '/dev/esp',
        ]
        for device_path in device_paths:
            if os.path.exists(device_path) and os.stat(device_path).st_gid > 0:
                return device_path

    def connect(self) -> None:
        if not self.serial.isOpen():
            self.serial.open()
            self.log.debug(f'reconnected serial on {self.device_path}')

    def disconnect(self) -> None:
        if self.serial.isOpen():
            self.serial.close()
            self.log.debug(f'disconnected serial on {self.device_path}')

    async def read(self) -> Optional[str]:
        if not self.serial.isOpen():
            return
        s = self.serial.read_all()
        s = s.decode()
        self.buffer += s
        if '\n' in self.buffer:
            line, self.buffer = self.buffer.split('\r\n', 1)
            if self.log_io:
                self.log.debug(f'read: {line}')
            return line

    async def send(self, line: str) -> None:
        if not self.serial.isOpen():
            return
        self.serial.write(f'{line}\n'.encode())
        if self.log_io:
            self.log.debug(f'send: {line}')

    def debug_ui(self) -> None:
        super().debug_ui()
        ui.switch(
            'Serial Communication', value=self.serial.isOpen(),
            on_change=self.toggle_communication)
        ui.switch('Serial Logging').bind_value(self, 'log_io')
        self.input = ui.input(on_change=self.submit_message)

    async def submit_message(self):
        await self.send_async(self.input.value)
        self.input.value = ''
        await self.input.view.update()

    async def toggle_communication(self, status):
        if status.value:
            self.connect()
            await rosys.notify('connected to Lizard')
        else:
            self.disconnect()
            await rosys.notify('disconnected from Lizard')
