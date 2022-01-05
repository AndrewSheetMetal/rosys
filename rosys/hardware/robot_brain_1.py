from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel
import abc
import asyncio
from ..communication import Communication
from ..world import Velocity, World
from .hardware import Hardware
from operator import ixor
from functools import reduce


class RobotBrain1(Hardware):

    def __init__(self, world: World, configuration: List[HardwareGroup], communication: Optional[Communication] = ...):
        super().__init__(world, communication=communication)
        self.configuration = configuration

    async def configure(self):
        await super().configure()
        await self.communication.send_async('esp erase')

        for group in self.configuration:
            for command in group.commands:
                await self.communication.send_async('+' + command)
                await asyncio.sleep(0.1)

        output_modules = ','.join(group.name for group in self.configuration if group.output)
        await self.communication.send_async(f'+set esp.outputModules={output_modules}')
        await self.communication.send_async('+esp unmute')
        await self.communication.send_async('+set esp.ready=1')
        await self.communication.send_async('+set esp.24v=1')
        await self.communication.send_async('esp restart')

    async def restart(self):
        await super().restart()
        await self.communication.send_async('esp restart')

    async def drive(self, linear: float, angular: float):
        super().drive(linear, angular)
        await self.communication.send_async('wheels speed %.3f,%.3f' % (linear, angular))

    async def stop(self):
        await super().stop()
        await self.communication.send_async('wheels power 0,0')

    async def update(self):
        await super().update()
        while True:
            line = await self.communication.read()
            if line is None:
                break
            if line.startswith("\x1b[0;32m"):
                self.log.warning(line)
                continue  # NOTE: ignore green log messages
            if '^' in line:
                line, checksum = line.split('^')
                if reduce(ixor, map(ord, line)) != int(checksum):
                    self.log.warning('Checksum failed')
                    continue
            if not line.startswith("esp "):
                self.log.warning(line)
                continue  # NOTE: ignore all messages but esp status
            try:
                words = line.split()[1:]
                millis = float(words.pop(0))
                if self.world.robot.clock_offset is None:
                    continue
                self.world.robot.hardware_time = millis / 1000 + self.world.robot.clock_offset
                for group in self.configuration:
                    if group.output:
                        group.parse(words, self.world)
            except (IndexError, ValueError):
                self.log.warning(f'Error parsing esp message "{line}"')

        if millis is not None:
            self.world.robot.clock_offset = self.world.time - millis / 1000


class HardwareGroup(BaseModel, abc.ABC):
    name: str
    output: bool = False

    @abc.abstractproperty
    def commands(self) -> list[str]:
        pass

    def with_output(self):
        self.output = True
        return self

    def parse(self, words: list[str], world: World):
        pass


class Bluetooth(HardwareGroup):
    device_name: str

    def __init__(self, **data):
        super().__init__(name='bluetooth', **data)

    @property
    def commands(self) -> list[str]:
        return [
            f'new bluetooth {self.name} ESP_{self.device_name}',
        ]


class Can(HardwareGroup):
    rxPin: str
    txPin: str

    def __init__(self, **data):
        super().__init__(name='can', **data)

    @property
    def commands(self) -> list[str]:
        return [
            f'new can {self.name} {self.rxPin},{self.txPin}',
        ]


class Led(HardwareGroup):
    pin: str
    interval: float = 0.1
    duty: float = 0.5
    repeat: bool = True

    @property
    def commands(self) -> list[str]:
        return [
            f'new led {self.name} {self.pin}',
            f'set {self.name}.interval={self.interval}',
            f'set {self.name}.duty={self.duty}',
            f'set {self.name}.repeat={"1" if self.repeat else "0"}',
        ]


class Button(HardwareGroup):
    pin: str

    @property
    def commands(self) -> list[str]:
        return [
            f'new button {self.name} {self.pin}',
        ]


class RoboClawWheels(HardwareGroup):
    address: int = 128
    baud: int = 38400
    m_per_tick: float
    width: float

    @property
    def commands(self) -> list[str]:
        return [
            f'new roboclawwheels {self.name} {self.address},{self.baud}',
            f'set {self.name}.mPerTick={self.m_per_tick}',
            f'set {self.name}.width={self.width}',
        ]

    def parse(self, words: list[str], world: World):
        world.robot.odometry.append(Velocity(
            linear=float(words.pop(0)),
            angular=float(words.pop(0)),
            time=world.robot.hardware_time,
        ))
        world.robot.temperature = float(words.pop(0))
        world.robot.battery = float(words.pop(0))


class ODriveMotor(HardwareGroup):
    can: Can
    device_id: int
    m_per_tick: float

    @property
    def commands(self) -> list[str]:
        return [
            f'new odrivemotor {self.name} 0,{self.can.name},{hex(self.device_id)[2:]}',
            f'set {self.name}.mPerTick={self.m_per_tick}',
        ]


class ODriveWheels(HardwareGroup):
    left: ODriveMotor
    right: ODriveMotor
    width: float
    left_power_factor: float = 1.0
    right_power_factor: float = 1.0

    @property
    def commands(self) -> list[str]:
        return self.left.commands + self.right.commands + [
            f'new odrivewheels {self.name} {self.left.name},{self.right.name}',
            f'set {self.name}.width={self.width}',
            f'set {self.name}.leftPowerFactor={self.left_power_factor}',
            f'set {self.name}.rightPowerFactor={self.right_power_factor}',
        ]

    def parse(self, words: list[str], world: World):
        world.robot.odometry.append(Velocity(
            linear=float(words.pop(0)),
            angular=float(words.pop(0)),
            time=world.robot.hardware_time,
        ))
