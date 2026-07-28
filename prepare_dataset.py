"""
Script untuk mempersiapkan dataset training YOLOv8 Classification
untuk deteksi APD: Helm Safety, Sepatu Safety, Sarung Tangan

Struktur dataset yang dibutuhkan:
dataset/
├── train/
│   ├── helm_safety/        ← Foto orang pakai helm
│   ├── sepatu_safety/      ← Foto orang pakai sepatu safety
│   ├── sarung_tangan/      ← Foto orang pakai sarung tangan
│   └── tidak_lengkap/      ← Foto TANPA APD (negative sample)
├── val/
│   ├── helm_safety/
│   ├── sepatu_safety/
│   ├── sarung_tangan/
│   └── tidak_lengkap/
└── test/
    ├── helm_safety/
    ├── sepatu_safety/
    ├── sarung_tangan/
    └── tidak_lengkap/

Cara pakai:
    python prepare_dataset.py --source /path/to/fotos --output dataset
"""

import os
import shutil
import argparse
import random
from pathlib import Path


CLASSES = ['helm_safety', 'sepatu_safety', 'sarung_tangan', 'tidak_lengkap']
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}


def create_dataset_structure(output_path):
    for split in ['train', 'val', 'test']:
        for cls in CLASSES:
            dir_path = os.path.join(output_path, split, cls)
            os.makedirs(dir_path, exist_ok=True)
            print(f"  Created: {dir_path}")


def scan_images(source_path):
    images = {}
    for cls in CLASSES:
        cls_dir = os.path.join(source_path, cls)
        if not os.path.exists(cls_dir):
            print(f"  Warning: Folder '{cls}' tidak ditemukan di source")
            images[cls] = []
            continue

        img_files = [
            f for f in os.listdir(cls_dir)
            if Path(f).suffix.lower() in IMAGE_EXTS
        ]
        images[cls] = [os.path.join(cls_dir, f) for f in img_files]
        print(f"  {cls}: {len(img_files)} gambar ditemukan")

    return images


def split_and_copy(images, output_path, train_ratio=0.7, val_ratio=0.15):
    for cls, files in images.items():
        if not files:
            continue

        random.shuffle(files)
        total = len(files)
        train_end = int(total * train_ratio)
        val_end = int(total * (train_ratio + val_ratio))

        splits = {
            'train': files[:train_end],
            'val': files[train_end:val_end],
            'test': files[val_end:]
        }

        for split, split_files in splits.items():
            dest_dir = os.path.join(output_path, split, cls)
            for f in split_files:
                dest = os.path.join(dest_dir, os.path.basename(f))
                shutil.copy2(f, dest)

            print(f"  {split}/{cls}: {len(split_files)} gambar")


def create_dataset_yaml(output_path):
    yaml_content = f"""# Dataset Configuration for APD Classification
# YOLOv8 Classification Model

path: {os.path.abspath(output_path)}
train: train
val: val
test: test

nc: {len(CLASSES)}
names: {CLASSES}
"""
    yaml_path = os.path.join(output_path, 'dataset.yaml')
    with open(yaml_path, 'w') as f:
        f.write(yaml_content)
    print(f"\n  Dataset YAML created: {yaml_path}")


def main():
    parser = argparse.ArgumentParser(description='Prepare APD Dataset for YOLOv8 Training')
    parser.add_argument('--source', '-s', required=True, help='Path ke folder sumber gambar')
    parser.add_argument('--output', '-o', default='dataset', help='Path output dataset (default: dataset)')
    parser.add_argument('--train-ratio', type=float, default=0.7, help='Rasio train (default: 0.7)')
    parser.add_argument('--val-ratio', type=float, default=0.15, help='Rasio val (default: 0.15)')
    args = parser.parse_args()

    print("=" * 60)
    print("  PREPARE DATASET - APD Classification (YOLOv8)")
    print("=" * 60)

    print(f"\n[1] Membuat struktur folder...")
    create_dataset_structure(args.output)

    print(f"\n[2] Scanning gambar dari: {args.source}")
    images = scan_images(args.source)

    total = sum(len(v) for v in images.values())
    if total == 0:
        print("\n  ERROR: Tidak ada gambar ditemukan!")
        print("  Pastikan source folder memiliki subfolder:")
        for cls in CLASSES:
            print(f"    - {cls}/")
        return

    print(f"\n  Total gambar: {total}")

    print(f"\n[3] Splitting dataset...")
    split_and_copy(images, args.output, args.train_ratio, args.val_ratio)

    create_dataset_yaml(args.output)

    print(f"\n[4] Selesai!")
    print(f"  Dataset tersimpan di: {os.path.abspath(args.output)}")
    print(f"\n  Selanjutnya jalankan: python train_model.py")


if __name__ == '__main__':
    main()
