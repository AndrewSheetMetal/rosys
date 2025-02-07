from dataclasses import dataclass, field
from typing import Optional
from uuid import uuid4

import numpy as np

from .. import rosys
from ..geometry import Point3d
from .camera_provider import CameraProvider
from .detections import BoxDetection, Detections, PointDetection
from .detector import Autoupload, Detector
from .image import Image
from .uploads import Uploads


@dataclass(slots=True, kw_only=True)
class SimulatedObject:
    category_name: str
    position: Point3d
    size: Optional[tuple[float, float, float]] = None
    uuid: str = field(init=False)
    confidence: float = 1.0

    def __post_init__(self) -> None:
        self.uuid = str(uuid4())


class DetectorSimulation(Detector):
    """This detector simulates object detection.

    It requires a camera provider in order to check visibility using the cameras' calibrations.
    Individual camera IDs can be added to a set of `blocked_cameras` to simulate occlusions during pytests.
    A list of `simulated_objects` can be filled to define what can be detected.
    An optional `noise` parameter controls the spatial accuracy in pixels.
    """

    def __init__(self, camera_provider: CameraProvider, *, noise: float = 1.0) -> None:
        super().__init__()

        self.camera_provider = camera_provider
        self.noise = noise

        self.blocked_cameras: set[str] = set()
        self.simulated_objects: list[SimulatedObject] = []
        self._uploads = Uploads()

        rosys.on_repeat(self.step, 0.1)

    @property
    def uploads(self) -> Uploads:
        return self._uploads

    def step(self) -> None:
        self._uploads.queue.clear()
        self._uploads.priority_queue.clear()

    async def detect(self, image: Image, autoupload: Autoupload = Autoupload.FILTERED, tags: list[str] = []) -> Optional[Detections]:
        is_blocked = image.camera_id in self.blocked_cameras
        await rosys.sleep(0.4)
        image.detections = Detections()
        if not is_blocked:
            self.update_simulated_objects(image)
            self.detect_from_simulated_objects(image)
        self.NEW_DETECTIONS.emit(image)
        return image.detections

    async def upload(self, image: Image) -> None:
        self.log.info(f'Uploading {image.id}')
        await super().upload(image)

    def update_simulated_objects(self, image: Image) -> None:
        pass

    def detect_from_simulated_objects(self, image: Image) -> None:
        if image.camera_id not in self.camera_provider.cameras:
            return
        camera = self.camera_provider.cameras[image.camera_id]
        assert camera.calibration is not None
        assert image.detections is not None
        for object in self.simulated_objects:
            viewing_direction = np.array(camera.calibration.extrinsics.rotation.R)[:, 2]
            object_direction = np.array(object.position.tuple) - camera.calibration.extrinsics.translation
            if np.dot(viewing_direction, object_direction) < 0:
                continue
            image_point = camera.calibration.project_to_image(object.position)
            if not (0 <= image_point.x < image.size.width and 0 <= image_point.y < image.size.height):
                continue

            if object.size is None:
                image.detections.points.append(PointDetection(
                    category_name=object.category_name,
                    model_name='simulation',
                    confidence=object.confidence,
                    x=image_point.x + self.noise * np.random.randn(),
                    y=image_point.y + self.noise * np.random.randn(),
                    uuid=object.uuid,
                ))
            else:
                world_points = np.array([
                    [object.position.x + dx, object.position.y + dy, object.position.z + dz]
                    for dx in [-object.size[0] / 2, object.size[0] / 2]
                    for dy in [-object.size[1] / 2, object.size[1] / 2]
                    for dz in [-object.size[2] / 2, object.size[2] / 2]
                ])
                image_points = camera.calibration.project_array_to_image(world_points)
                image.detections.boxes.append(BoxDetection(
                    category_name=object.category_name,
                    model_name='simulation',
                    confidence=object.confidence,
                    x=image_points[:, 0].min() + self.noise * np.random.randn(),
                    y=image_points[:, 1].min() + self.noise * np.random.randn(),
                    width=image_points[:, 0].max() - image_points[:, 0].min() + self.noise * np.random.randn(),
                    height=image_points[:, 1].max() - image_points[:, 1].min() + self.noise * np.random.randn(),
                    uuid=object.uuid,
                ))
