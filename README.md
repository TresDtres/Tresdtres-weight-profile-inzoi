# PureQ Weight Transfer for InZOI

Advanced Blender add-on for transferring clean avatar weights to garments with profile-based workflows and manual one-shot support.

## What This Add-on Does

- Transfers weights from avatar mesh to clothing mesh
- Supports profile-driven transfer (`Model Profile` / `Bone Profile`)
- Supports one-shot transfer without creating profiles (manual bone mask)
- Includes contamination-reduction workflow (double-pass cleanup)
- Includes profile manager tools (create/edit/import/export)
- Includes diagnostics and post-transfer cleanup tools

## Key Workflow Modes

1. Quick one-shot:
- Set avatar
- Import/select clothing
- Load/select bones manually
- Transfer once, no profile creation required

2. Reusable production workflow:
- Create/select a `Model Profile` in Profile Manager
- Reuse it across similar garments
- Transfer with consistent bone scope and settings

## Documentation

- Installation guide: [INSTALL.md](INSTALL.md)
- User manual: [USER_MANUAL.md](USER_MANUAL.md)

## Compatibility

- Blender 4.2+

## Project Structure (Release)

- Core add-on code at repository root and `core/`
- Profile and taxonomy data in `data/`
- Preset resources in `presets/`

## License

Apache-2.0 (see add-on metadata in `__init__.py`).
# Tresdtres-weight-profile-inzoi
