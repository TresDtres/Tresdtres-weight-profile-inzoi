# User Manual

## 1. Main Concepts

- `Model Profile`:
  - Garment-oriented reusable profile (type/style/metadata + transfer profile payload).
- `Bone Profile`:
  - Bone template used for transfer masking.
- `Bone Mask (Manual Filter)`:
  - One-shot manual selection of bones for transfer.

Transfer source priority:
1. `Model Profile` (if selected and valid)
2. `Bone Profile` (if selected)
3. Manual bone mask (if bones are enabled in list)

## 2. Basic One-Shot Workflow (No Profile Creation)

1. Set avatar:
   - Use `Find Avatar` or `Set Avatar from Selection`.
2. Import/select clothing mesh:
   - Use `Load Clothing` or select garment and set from selection.
3. Load or define bone mask:
   - Select `Bone Profile` and click `Load Bone Mask from Profile`, or manually adjust enabled bones.
4. Click `Transfer Weights`.
5. Optionally run cleanup/smoothing tools.

## 3. Reusable Workflow with Model Profiles

1. Switch `Mode` to `Profile Manager`.
2. Create or select a `Model Profile`.
3. Save profile settings and bone definition.
4. Return to `Transfer` mode.
5. Select the same `Model Profile` and transfer.

## 4. Transfer Settings

- `Method`:
  - `Nearest Face Interpolated`: smoother in most cases.
  - `Nearest Vertex`: fallback for difficult topology.
- `Double-pass contamination cleanup`:
  - Helps reduce weight contamination by restricting transfer to detected garment-relevant vertices.
- `Seed threshold`:
  - Lower values include more seed vertices in double-pass mode.

## 5. Diagnostics and Cleanup

- Use diagnostics before/after transfer to inspect results.
- Cleanup tools include:
  - smooth/clean
  - clear weights
  - merge similar groups
  - low-weight selection
  - weight compensation

## 6. Best Practices

- Keep avatar and garment aligned in scale and position.
- Use reusable profiles for production consistency.
- Use one-shot manual mode for quick experiments or one-off assets.
- Save profile only when you need reuse.
