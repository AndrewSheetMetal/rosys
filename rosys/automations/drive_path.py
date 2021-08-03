import numpy as np
from ..world.point import Point
from ..world.spline import Spline
from ..world.world import World
from ..actors.esp import Esp
from .spline import drive_spline, throttle, eliminate_2pi


async def drive_path(world: World, esp: Esp):

    for s, spline in enumerate(world.path):
        if s == 0 or spline.start.distance(world.path[s-1].end) > 0.01:
            await drive_to(world, esp, spline.start)
        await drive_spline(spline, world, esp)


async def drive_to(world: World, esp: Esp, target: Point):

    if world.robot.parameters.minimum_turning_radius:
        await drive_circle(world, esp, target)

    robot_pose = world.robot.prediction
    approach_spline = Spline(
        start=robot_pose.point,
        control1=robot_pose.point.interpolate(target, 1/3),
        control2=robot_pose.point.interpolate(target, 2/3),
        end=target,
    )
    await drive_spline(approach_spline, world, esp)


async def drive_circle(world: World, esp: Esp, target: Point):

    while True:
        direction = world.robot.prediction.point.direction(target)
        angle = eliminate_2pi(direction - world.robot.prediction.yaw)
        if abs(angle) < np.deg2rad(5):
            break
        linear = 0.5
        sign = 1 if angle > 0 else -1
        angular = linear / world.robot.parameters.minimum_turning_radius * sign
        await esp.drive(*throttle(world, linear, angular))
