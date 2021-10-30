from nicegui.ui import Ui
from rosys.runtime import Runtime
from .joystick import Joystick as joystick
from .robot_object import RobotObject as robot_object
from .keyboard_control import KeyboardControl as keyboard_control


def configure(ui: Ui, runtime: Runtime):
    ui.on_startup(runtime.start())
    ui.on_shutdown(runtime.stop())
    joystick.steerer = runtime.steerer
    keyboard_control.ui = ui
    keyboard_control.steerer = runtime.steerer
    robot_object.robot = runtime.world.robot
