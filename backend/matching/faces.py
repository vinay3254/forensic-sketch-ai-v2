"""Face fingerprints for suspect matching: MediaPipe finds the face and its eye, nose and mouth points, the face
is aligned to ArcFace's standard 112x112 layout, and ArcFace (InsightFace w600k_r50, ONNX on CPU) turns it into
512 numbers. Two fingerprints are compared by cosine similarity: same person ~0.4 and up, different people ~0.1."""

import io
from pathlib import Path
from typing import Protocol

import numpy as np
from PIL import Image

# ArcFace's reference points in a 112x112 face: the eye on the image's left, the other eye, nose tip, mouth centre
TEMPLATE = np.array([[38.2946, 51.6963], [73.5318, 51.5014], [56.0252, 71.7366], [56.1396, 92.2848]], np.float64)


class NoFace(ValueError):
    pass


class Embedder(Protocol):
    def embed(self, image: bytes) -> np.ndarray: ...  # unit vector; raises NoFace


def similarity_transform(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    """2x3 matrix (rotation + uniform scale + shift) taking src points onto dst points (Umeyama)."""
    mu_s, mu_d = src.mean(0), dst.mean(0)
    s, d = src - mu_s, dst - mu_d
    u, sig, vt = np.linalg.svd(d.T @ s / len(src))
    e = np.diag([1, np.sign(np.linalg.det(u @ vt))])
    r = u @ e @ vt
    scale = (sig * np.diag(e)).sum() / s.var(0).sum()
    m = np.zeros((2, 3))
    m[:, :2] = scale * r
    m[:, 2] = mu_d - scale * r @ mu_s
    return m


def align(img: Image.Image, points: np.ndarray) -> Image.Image:
    m = similarity_transform(points, TEMPLATE)
    inv = np.linalg.inv(np.vstack([m, [0, 0, 1]]))[:2]  # PIL maps output pixels back to input pixels
    return img.transform((112, 112), Image.AFFINE, inv.ravel().tolist(), resample=Image.BILINEAR)


class ArcFaceEmbedder:
    def __init__(self, arcface: Path, detector: Path):
        import mediapipe as mp
        import onnxruntime

        self.session = onnxruntime.InferenceSession(str(arcface), providers=["CPUExecutionProvider"])
        self.input = self.session.get_inputs()[0].name
        opts = mp.tasks.vision.FaceDetectorOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(detector)), min_detection_confidence=0.4)
        self.detector = mp.tasks.vision.FaceDetector.create_from_options(opts)
        self._mp = mp

    def points(self, img: Image.Image) -> np.ndarray:
        """Eye on the image's left, other eye, nose tip, mouth centre of the largest face, in pixels."""
        rgb = np.asarray(img.convert("RGB"))
        found = self.detector.detect(self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)).detections
        if not found:
            raise NoFace("No face found in the picture.")
        best = max(found, key=lambda d: d.bounding_box.width * d.bounding_box.height)
        kp = [(k.x * img.width, k.y * img.height) for k in best.keypoints[:4]]
        eyes = sorted(kp[:2])  # the eye nearer the image's left first
        return np.array([*eyes, kp[2], kp[3]], np.float64)

    def embed(self, image: bytes) -> np.ndarray:
        img = Image.open(io.BytesIO(image)).convert("RGB")
        face = np.asarray(align(img, self.points(img)), np.float32)
        x = ((face - 127.5) / 127.5).transpose(2, 0, 1)[None]
        v = self.session.run(None, {self.input: x})[0][0].astype(np.float32)
        return v / np.linalg.norm(v)
