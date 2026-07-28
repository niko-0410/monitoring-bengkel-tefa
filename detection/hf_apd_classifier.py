import cv2
import numpy as np
from PIL import Image
import time
import os

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"


class HFApdClassifier:
    """
    Klasifikasi APD menggunakan Hugging Face CLIP (zero-shot).
    Pipeline: YOLOv8 detect person -> crop body regions -> CLIP classify APD.
    """

    LABEL_MAP = {
        'head': {
            'positive': [
                'a photo of a safety helmet',
                'a photo of a hard hat',
                'a photo of a construction helmet',
                'a photo of a person wearing a helmet',
                'a photo of a yellow safety helmet',
                'a photo of a white hard hat',
            ],
            'negative': [
                'a photo of a bare head with hair',
                'a photo of a person without helmet',
                'a photo of bare hair',
            ],
            'apd_type': 'helm',
        },
        'feet': {
            'positive': [
                'a photo of safety shoes',
                'a photo of work boots',
                'a photo of steel toe boots',
                'a photo of heavy duty boots',
                'a photo of black work boots',
                'a photo of safety boots',
            ],
            'negative': [
                'a photo of bare feet',
                'a photo of sandals',
                'a photo of regular sneakers',
                'a photo of flip flops',
            ],
            'apd_type': 'sepatu',
        },
        'hands': {
            'positive': [
                'a photo of safety gloves',
                'a photo of work gloves',
                'a photo of protective gloves',
                'a photo of leather gloves',
                'a photo of cotton gloves',
                'a photo of rubber gloves',
            ],
            'negative': [
                'a photo of bare hands',
                'a photo of hands without gloves',
                'a photo of skin colored hands',
            ],
            'apd_type': 'sarungtangan',
        },
    }

    def __init__(self, model_name="openai/clip-vit-base-patch32"):
        self.model_name = model_name
        self.pipe = None
        self.loaded = False

    def load(self):
        try:
            from transformers import pipeline
            print(f"[HF] Loading CLIP model: {self.model_name} ...")
            self.pipe = pipeline(
                task="zero-shot-image-classification",
                model=self.model_name,
                device=-1,
            )
            self.loaded = True
            print(f"[HF] CLIP model loaded successfully")
            return True
        except Exception as e:
            print(f"[HF] Failed to load CLIP: {e}")
            self.loaded = False
            return False

    def classify_region(self, crop_bgr, region_name):
        if not self.loaded or self.pipe is None:
            return None, 0.0

        labels_info = self.LABEL_MAP.get(region_name)
        if labels_info is None:
            return None, 0.0

        rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)

        all_labels = labels_info['positive'] + labels_info['negative']

        try:
            t0 = time.time()
            results = self.pipe(pil_img, candidate_labels=all_labels, top_k=5)
            elapsed = time.time() - t0

            pos_score = 0.0
            neg_score = 0.0
            for r in results:
                if r['score'] is None:
                    continue
                label = r['label']
                score = float(r['score'])
                if label in labels_info['positive']:
                    pos_score += score
                else:
                    neg_score += score

            detected = pos_score > neg_score
            confidence = pos_score if detected else neg_score
            apd_type = labels_info['apd_type'] if detected else None

            return apd_type, confidence

        except Exception as e:
            print(f"[HF] Classification error ({region_name}): {e}")
            return None, 0.0

    def classify_person(self, frame, x1, y1, x2, y2, frame_w, frame_h):
        results = {}
        regions = self._extract_regions(x1, y1, x2, y2, frame_w, frame_h)

        for region_name, (rx1, ry1, rx2, ry2) in regions.items():
            crop = frame[ry1:ry2, rx1:rx2]
            if crop.size == 0:
                results[region_name] = {'apd_type': None, 'confidence': 0.0, 'bbox': (rx1, ry1, rx2, ry2)}
                continue

            apd_type, conf = self.classify_region(crop, region_name)
            results[region_name] = {'apd_type': apd_type, 'confidence': conf, 'bbox': (rx1, ry1, rx2, ry2)}

        return results

    def _extract_regions(self, x1, y1, x2, y2, frame_w, frame_h):
        pw = x2 - x1
        ph = y2 - y1
        cx = x1 + pw // 2

        head_y1 = max(0, y1)
        head_y2 = min(frame_h, y1 + int(ph * 0.28))
        head_x1 = max(0, cx - int(pw * 0.35))
        head_x2 = min(frame_w, cx + int(pw * 0.35))

        feet_y1 = max(0, y2 - int(ph * 0.22))
        feet_y2 = min(frame_h, y2)
        feet_x1 = max(0, cx - int(pw * 0.4))
        feet_x2 = min(frame_w, cx + int(pw * 0.4))

        hand_y1 = max(0, y1 + int(ph * 0.30))
        hand_y2 = min(frame_h, y1 + int(ph * 0.65))
        margin = int(pw * 0.1)
        hand_x1 = max(0, x1 - margin)
        hand_x2 = min(frame_w, x2 + margin)

        return {
            'head': (head_x1, head_y1, head_x2, head_y2),
            'feet': (feet_x1, feet_y1, feet_x2, feet_y2),
            'hands': (hand_x1, hand_y1, hand_x2, hand_y2),
        }
