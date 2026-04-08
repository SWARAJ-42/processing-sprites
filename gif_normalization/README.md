# gif_normalization

Preprocessing pipeline for GIF-based game character animations.  
Prepares data for **LTX 2.3 I2V training** (captions, no audio).

---

## Directory layout

```
gif_normalization/
├── preprocess/
│   ├── frame_normalization.py      # 8N+1 frame count normalisation
│   ├── resolution_normalization.py # Pad + scale to ×32, min 512 px
│   └── transparency_handling.py    # Replace alpha with high-contrast bg
│
├── pipeline/
│   └── run_pipeline.py             # End-to-end runner + CLI
│
├── test/
│   └── test_preprocess.py          # Manual inspection tests
│
├── test_results/                   # Output directory for test runs
│
└── utils/
    └── io_utils.py                 # GIF I/O helpers
```

---

## Requirements

```
Pillow>=10.0
numpy>=1.24
```

Install:
```bash
pip install Pillow numpy
```

---

## Run the full pipeline

```bash
python gif_normalization/pipeline/run_pipeline.py ./raw_assets/input_dir_1
```

This will create `./raw_assets/input_dir_1/dataset/` containing:
- All processed GIFs (named `0001_<relative_path_slug>.gif`)
- `metadata.json`

### Parallel workers

```bash
python gif_normalization/pipeline/run_pipeline.py ./raw_assets/input_dir_1 --workers 4
```

---

## Test individual preprocessing steps

```bash
python gif_normalization/test/test_preprocess.py <gif_path> <operation>
```

Available operations:
- `transparency_handling`
- `frame_normalization`
- `resolution_normalization`

Output is saved to `gif_normalization/test_results/<operation>_<timestamp>.gif`.

Example:
```bash
python gif_normalization/test/test_preprocess.py raw_assets/input_dir_1/run/c.gif frame_normalization
```

---

## Metadata schema

Each entry in `metadata.json`:

```json
{
  "media_path":    "./dataset/0001_attack_a.gif",
  "original_path": "./attack/a.gif",
  "width":         256,
  "height":        256,
  "num_frames":    17,
  "resolution":    256,
  "bgcolor":       "#00ff00",
  "caption":       "",
  "warnings":      ["frame_normalization: upsampled 8 → 9 frames."]
}
```

`resolution` is bucketed to one of: `256 | 512 | 768 | 1024 | 1280 | 1328 | 1538`  
(nearest bucket to `sqrt(width × height)`).

---

## Extending the pipeline

1. Add your new module under `preprocess/` following the same signature pattern:

   ```python
   def my_step(frames, ...) -> (frames, ..., warnings: List[str]):
       ...
   ```

2. In `pipeline/run_pipeline.py`, import your module and call it inside
   `_process_single_gif` in the clearly marked *"preprocessing steps"* block.

3. Thread any new metadata fields through the returned dict.
