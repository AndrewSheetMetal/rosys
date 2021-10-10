from __future__ import annotations
from asyncio.exceptions import CancelledError
from rosys import factory
import sys
import asyncio
import logging
from typing import Awaitable, Callable, Optional, Type, Union, get_type_hints
from . import task_logger
from .persistence import Persistence
from .actors.actor import Actor
from .actors.detector import Detector
from .actors.detector_simulator import DetectorSimulator
from .actors.odometer import Odometer
from .actors.steerer import Steerer
from .actors.robot_locator import RobotLocator
from .actors.automator import Automator
from .actors.camera_scanner import CameraScanner
from .actors.camera_downloader import CameraDownloader
from .actors.camera_linker import CameraLinker
from .actors.camera_simulator import CameraSimulator
from .actors.camera_projector import CameraProjector
from .actors.tracker import Tracker
from .world.world import World, WorldState
from .world.mode import Mode
from .helpers import print_stacktrace


class Runtime:

    def __init__(self, world: World, persistence: Optional[Persistence] = None):
        self.world = world
        self.tasks = []
        self.log = logging.getLogger(__name__)

        if self.world.mode != Mode.TEST:
            self.persistence = persistence or Persistence(world)
            self.persistence.restore()

        self.esp = factory.create_esp(world)
        self.log.info(f'selected {type(self.esp).__name__}')
        self.odometer = Odometer()
        self.steerer = Steerer()
        self.automator = Automator()

        self.actors = [
            self.esp,
            self.odometer,
            self.steerer,
            self.automator,
        ]

        self.follow_ups = {
            self.esp.step: [
                self.odometer.handle_velocity,
            ],
        }

    def with_cameras(self) -> Runtime:
        if self.world.mode == Mode.REAL:
            self.actors += [CameraScanner(), CameraDownloader()]
            self.detector = Detector()
        else:
            self.actors += [CameraSimulator()]
            self.detector = DetectorSimulator()

        self.camera_projector = CameraProjector()
        self.camera_linker = CameraLinker()
        self.tracker = Tracker(self.world)
        self.robot_locator = RobotLocator()
        self.actors += [
            self.camera_projector,
            self.camera_linker,
            self.tracker,
            self.detector,
            self.robot_locator,
        ]

        self.follow_ups[self.detector.step] = [
            self.robot_locator.find_robot,
            self.odometer.handle_detection,
        ]

        return self

    def with_actors(self, *actors: list[Actor]):
        self.actors += actors
        return self

    async def pause(self):
        self.world.state = WorldState.PAUSED
        await self.esp.drive(0, 0)

    def resume(self):
        self.world.state = WorldState.RUNNING

    async def run(self, seconds: float = sys.maxsize):
        if self.tasks:
            raise Exception('run should be only executed once')

        end_time = self.world.time + seconds

        for actor in self.actors:
            if actor.interval is not None:
                self.tasks.append(task_logger.create_task(self.repeat(actor, end_time)))

    async def stop(self):
        if self.world.mode != Mode.TEST:
            self.persistence.backup()
        [t.cancel() for t in self.tasks]
        await asyncio.gather(*[task_logger.create_task(a.tear_down()) for a in self.actors])

    async def call_follow_ups(self, trigger: Union[Callable, Awaitable]):
        for follow_up in self.follow_ups.get(trigger, []):
            params = self.get_params(follow_up)
            await follow_up(*params) if asyncio.iscoroutine(follow_up) else follow_up(*params)
            await self.call_follow_ups(follow_up)

    async def repeat(self, actor: Actor, run_end_time: float):
        params = self.get_params(actor.step)

        while self.world.time < run_end_time:
            start = self.world.time
            try:
                await actor.step(*params)
                await self.call_follow_ups(actor.step)
                dt = self.world.time - start
            except (CancelledError, GeneratorExit):
                return
            except:
                dt = self.world.time - start
                self.log.exception(f'error in {actor}')
                if actor.interval == 0 and dt < 0.1:
                    delay = 0.1 - dt
                    self.log.warning(
                        f'{actor} would be called to frequently ' +
                        f'because it only took {dt*1000:.0f} ms; ' +
                        f'delaying this step for {delay*1000:.0f} ms')
                    await actor.sleep(delay)

            try:
                await actor.sleep(actor.interval - dt)
            except (CancelledError, GeneratorExit):
                return

    def get_actor(self, _type: Type):
        return next((a for a in self.actors if type(a) is _type), None)

    def get_params(self, func: Union[Callable, Awaitable]):
        params = []
        for name, type_ in get_type_hints(func).items():
            for obj in [self.world] + self.actors:
                if isinstance(obj, type_):
                    params.append(obj)
                    break
            else:
                raise Exception(f'parameter "{name}" of type {type_} is unknown')

        return params
