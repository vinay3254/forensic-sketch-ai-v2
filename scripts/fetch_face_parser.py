"""Download BiSeNet face-parsing weights and export them to storage/models/face_parser.onnx.

One-time setup for localized edits. Needs PyTorch, which the app itself does not use:
  uv run --with torch --with torchvision --with onnx python -m scripts.fetch_face_parser
Model code: zllrunning/face-parsing.PyTorch (MIT). Weights: trained on CelebAMask-HQ,
non-commercial research use only.
"""

import hashlib
import sys
import tempfile
import urllib.request
from pathlib import Path

from backend.config import get_settings

COMMIT = "d2e684cf1588b46145635e8fe7bcc29544e5537e"
CODE_URL = f"https://raw.githubusercontent.com/zllrunning/face-parsing.PyTorch/{COMMIT}/{{}}"
WEIGHTS_URL = "https://huggingface.co/vivym/face-parsing-bisenet/resolve/main/79999_iter.pth"
WEIGHTS_SHA256 = "468e13ca13a9b43cc0881a9f99083a430e9c0a38abd935431d1c28ee94b26567"


def main() -> None:
    import torch
    import torch.utils.model_zoo as modelzoo

    out = get_settings().storage_dir / "models" / "face_parser.onnx"
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for name in ("model.py", "resnet.py"):
            urllib.request.urlretrieve(CODE_URL.format(name), tmp / name)
        weights = tmp / "79999_iter.pth"
        print("Downloading weights (53 MB)...")
        urllib.request.urlretrieve(WEIGHTS_URL, weights)
        if hashlib.sha256(weights.read_bytes()).hexdigest() != WEIGHTS_SHA256:
            sys.exit("Weights checksum mismatch; not exporting.")
        modelzoo.load_url = lambda *a, **k: {}  # backbone weights are overwritten by the full checkpoint
        sys.path.insert(0, str(tmp))
        from model import BiSeNet

        net = BiSeNet(n_classes=19)
        net.load_state_dict(torch.load(weights, map_location="cpu", weights_only=True))
        net.eval()

        class FirstOutput(torch.nn.Module):
            def __init__(self, inner):
                super().__init__()
                self.inner = inner

            def forward(self, x):
                return self.inner(x)[0]

        torch.onnx.export(
            FirstOutput(net), torch.zeros(1, 3, 512, 512), str(out),
            input_names=["image"], output_names=["classes"], opset_version=17, dynamo=False,
        )
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
