"""
Script Training YOLOv8 Classification untuk APD Detection
Kelas: helm_safety, sepatu_safety, sarung_tangan, tidak_lengkap

Cara pakai:
    python train_model.py --data dataset --epochs 50 --imgsz 224

Model akan disimpan di: runs/classify/train/weights/best.pt
"""

import argparse
import os
import shutil
from pathlib import Path


def train(data_path, epochs, imgsz, batch_size, model_size, project, name):
    from ultralytics import YOLO

    print("=" * 60)
    print("  TRAINING YOLOv8 CLASSIFICATION - APD Detection")
    print("=" * 60)
    print(f"\n  Model base   : yolov8n-cls.pt ({model_size})")
    print(f"  Dataset      : {data_path}")
    print(f"  Epochs       : {epochs}")
    print(f"  Image size   : {imgsz}")
    print(f"  Batch size   : {batch_size}")
    print()

    model_name = f'yolov8{model_size}-cls.pt'
    model = YOLO(model_name)

    results = model.train(
        data=data_path,
        epochs=epochs,
        imgsz=imgsz,
        batch=batch_size,
        project=project,
        name=name,
        exist_ok=True,
        patience=20,
        save=True,
        verbose=True
    )

    best_weights = os.path.join(project, name, 'weights', 'best.pt')
    last_weights = os.path.join(project, name, 'weights', 'last.pt')

    models_dir = 'models'
    os.makedirs(models_dir, exist_ok=True)

    if os.path.exists(best_weights):
        dest = os.path.join(models_dir, 'apd_cls_best.pt')
        shutil.copy2(best_weights, dest)
        print(f"\n  Model terbaik disalin ke: {dest}")

    print("\n" + "=" * 60)
    print("  TRAINING SELESAI!")
    print("=" * 60)
    print(f"\n  Untuk menggunakan model, jalankan:")
    print(f"    python app.py")
    print(f"\n  Model akan otomatis dimuat dari: models/apd_cls_best.pt")

    return results


def main():
    parser = argparse.ArgumentParser(description='Train YOLOv8 Classification for APD Detection')
    parser.add_argument('--data', '-d', default='dataset', help='Path ke folder dataset (default: dataset)')
    parser.add_argument('--epochs', '-e', type=int, default=50, help='Jumlah epochs (default: 50)')
    parser.add_argument('--imgsz', type=int, default=224, help='Ukuran gambar (default: 224)')
    parser.add_argument('--batch', '-b', type=int, default=16, help='Batch size (default: 16)')
    parser.add_argument('--model', '-m', default='n', choices=['n', 's', 'm', 'l', 'x'],
                        help='Model size: n=nano, s=small, m=medium, l=large, x=xlarge (default: n)')
    parser.add_argument('--project', default='runs/classify', help='Project folder (default: runs/classify)')
    parser.add_argument('--name', default='apd_training', help='Experiment name (default: apd_training)')
    args = parser.parse_args()

    if not os.path.exists(args.data):
        print(f"  ERROR: Folder dataset '{args.data}' tidak ditemukan!")
        print(f"  Jalankan: python prepare_dataset.py --source /path/to/fotos --output {args.data}")
        return

    for split in ['train', 'val']:
        split_path = os.path.join(args.data, split)
        if not os.path.exists(split_path):
            print(f"  ERROR: Folder '{split_path}' tidak ditemukan!")
            return

    train(args.data, args.epochs, args.imgsz, args.batch, args.model, args.project, args.name)


if __name__ == '__main__':
    main()
