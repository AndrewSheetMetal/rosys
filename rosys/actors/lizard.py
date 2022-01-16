from .. import event
from ..hardware import Hardware
from . import Actor
import time


class Lizard(Actor):
    interval: float = 0.01

    def __init__(self, hardware: Hardware):
        super().__init__()
        self.hardware = hardware
        self.last_step = None
        event.register(event.Id.PAUSE_AUTOMATIONS, self._handle_pause)

    async def step(self):
        await self.ensure_responsiveness()
        await self.hardware.update()
        t = time.time()
        await event.call(event.Id.NEW_MACHINE_DATA)
        dt = time.time() - t
        if dt > 0.02:
            self.log.warning(f'computing machine data took {dt:.2f} s')

    async def _handle_pause(self, reason: str):
        await self.hardware.stop()

    async def ensure_responsiveness(self):
        dt = self.world.time - self.last_step if self.last_step is not None else 0
        if dt > 1:
            msg = f'esp serial communication can not be guaranteed ({dt:.2f} s since last call)'
            self.log.error(msg + '; aborting automations')
            await self.pause_automations(because=msg)
        elif dt > 0.1:
            self.log.warning(f'esp serial communication is slow ({dt:.2f} s since last call)')
        self.last_step = self.world.time
