# Installation Guide

## Option A: Install from ZIP (recommended for users)

1. Compress the add-on folder so that `__init__.py` is at the root of the ZIP.
2. In Blender, go to `Edit > Preferences > Add-ons`.
3. Click `Install...`.
4. Select the ZIP file.
5. Enable the add-on: `PureQ Weight Transfer`.

## Option B: Install from local folder (development)

1. Copy the project folder into Blender add-ons directory:
   - Windows: `%APPDATA%\Blender Foundation\Blender\<version>\scripts\addons\`
2. Restart Blender.
3. Open `Edit > Preferences > Add-ons`.
4. Search for `PureQ Weight Transfer` and enable it.

## Verify Installation

1. Open `3D Viewport`.
2. Open sidebar (`N` key).
3. Find tab: `PureQ Weight Transfer`.
4. You should see:
   - `Mode` selector
   - Avatar/Garment sections
   - Transfer and Profile controls

## Troubleshooting

- If UI is partially missing:
  - Disable and re-enable the add-on.
  - Restart Blender.
- If operator/class warnings appear:
  - Ensure only one copy of the add-on exists in Blender add-ons folders.
- If profiles are missing:
  - Confirm `data/bone_profiles.json` exists.
