# Injury Image Classification

A PyTorch transfer-learning classifier for injury/wound photos across **10 classes**:
`Abrasions, Bruises, Burns, Cut, Laceration, Normal, Pressure_wound, Stab_wound,
Surgical_wound, Venous_wound`.

> ⚠️ **Disclaimer:** This is a research/educational project, **not a medical device**.
> Predictions are not clinical advice and must not be used for diagnosis or treatment.

## Approach

This is a **full fine-tuning** pipeline tuned for accuracy (not a quick head-only pass):

- **Backbone:** EfficientNet-B0 pretrained on ImageNet by default (configurable via
  `--arch`: `efficientnet_b0`, `mobilenet_v3_large`, `mobilenet_v3_small`, `resnet50`).
- **Two-phase training:**
  1. *Warmup* — the backbone is frozen while the fresh classifier head settles.
  2. *Fine-tune* — the whole network trains with a **discriminative learning rate**
     (lower on the pretrained backbone, higher on the head), a **cosine schedule with
     linear warmup**, and strong augmentation.
- **EMA weights:** an exponential moving average of the weights is what gets evaluated
  and saved — consistently more accurate and stable than the raw training weights.
- **Strong augmentation:** `RandomResizedCrop`, flips, `TrivialAugmentWide`, and
  `RandomErasing` (cutout) for better generalization on a small dataset.
- **Class imbalance** (Stab_wound has only 23 images vs. Pressure_wound's 301) is handled
  with a **stratified train/val/test split**, a **class-weighted loss with label
  smoothing**, and by selecting the best model on **validation macro-F1** rather than
  accuracy. Early stopping (patience 12) ends training once val macro-F1 stops improving.

## Setup

```bash
pip install -r requirements.txt
# For a CPU-only machine, install the smaller CPU wheels:
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

## Data

> **The dataset is not included in this repository** (it is large and consists of
> real medical/wound photos whose license likely does not permit public
> redistribution). To train or evaluate, provide your own images in `Training_Data/`,
> one subfolder per class. A pre-trained model ships in `outputs/best_model.pt`, so
> inference (`predict.py`, `test_folder.py`) works without the dataset.

Expected layout — images in `Training_Data/`, one subfolder per class:

```
Training_Data/
├── Abrasions/
├── Bruises/
├── ...
└── Venous_wound/
```

The split is created once (stratified, seeded) and saved to `outputs/split.json`, so
training, evaluation, and re-runs all use the same test set.

## Usage

```bash
# Full training — default EfficientNet-B0, 60 epochs with early stopping.
# On a CPU this is roughly a 3-4 hour run (fewer if early stopping kicks in).
python train.py

# Live status bar (run in a SECOND terminal while training):
#   [######------------] 12/60 20.0% | fine-tune | best f1 0.85 | last f1 0.84 | ETA 1:12:03
python monitor.py

# Faster backbone (~1.5-2.5 h on CPU)
python train.py --arch mobilenet_v3_large

# Highest ceiling, heavy on CPU (overnight)
python train.py --arch resnet50

# Tune the schedule
python train.py --epochs 80 --warmup-epochs 4 --lr 1e-3

# Evaluate on the held-out test set (report + confusion matrix PNG)
python evaluate.py
python evaluate.py --tta        # test-time augmentation (orig + h-flip) for a small boost

# Classify a single image
python predict.py "Training_Data/Burns/burns (1).jpg" --topk 3

# Test a whole folder of images whose FILENAMES contain the class
# (e.g. bruise.jpg, stab_wound.jpg). Prints per-image results + accuracy,
# writes outputs/test_folder_results.csv. Defaults to ./test_data.
python test_folder.py
python test_folder.py path/to/folder --tta
```

Training is resumable in spirit but not checkpoint-resumable: it always keeps the single
best checkpoint by val macro-F1. You can safely stop a run early — the best model found so
far is already saved to `outputs/best_model.pt`.

## Key hyperparameters (`config.py`)

| Setting | Default | Meaning |
|---------|---------|---------|
| `ARCH` | `efficientnet_b0` | Default backbone |
| `EPOCHS` | 60 | Total epochs (warmup + fine-tune) |
| `WARMUP_EPOCHS` | 3 | Head-only epochs before unfreezing |
| `LR` | 1e-3 | Head learning rate |
| `BACKBONE_LR_MULT` | 0.1 | Backbone LR = `LR × this` |
| `EMA_DECAY` | 0.999 | Weight-averaging decay |
| `EARLY_STOPPING_PATIENCE` | 12 | Stop after N epochs without val-F1 gain |

## Outputs (written to `outputs/`)

| File | Description |
|------|-------------|
| `best_model.pt` | Best EMA checkpoint (by val macro-F1) + metadata (incl. arch) |
| `class_names.json` | Class ordering used by eval/predict |
| `split.json` | Persisted train/val/test indices |
| `training_log.csv` | Per-epoch phase/loss/accuracy/F1/LR |
| `confusion_matrix.png` | Test-set confusion matrix |

## Files

- `config.py` — paths, hyperparameters, seed, normalization constants
- `data.py` — stratified split, augmentation, class weights, dataloaders
- `model.py` — multi-backbone `build_model()`, param grouping, freeze/unfreeze helpers
- `train.py` — two-phase full fine-tuning with EMA, cosine schedule, early stopping
- `evaluate.py` — test metrics + confusion matrix (optional TTA)
- `predict.py` — single-image inference

## Notes on expected performance

With full fine-tuning of EfficientNet-B0 on ~1.2k training images, expect roughly
**80–90% overall test accuracy** (higher than a frozen-backbone baseline). `Stab_wound`
and `Cut` remain the weakest classes due to low sample counts; `Stab_wound`'s test metrics
in particular are high-variance (only a few test images). Watch **macro-F1**, not accuracy,
to judge minority-class performance.
