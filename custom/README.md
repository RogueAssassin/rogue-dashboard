# Custom Rogue Dashboard assets

This directory is mounted read-only into the dashboard container and survives image rebuilds.

- Put service icons in `custom/icons/` and use `/custom/icons/your-icon.svg` in the card editor.
- Put backgrounds in `custom/backgrounds/` and use `/custom/backgrounds/your-background.jpg` in Appearance settings.
- Recommended icon format: square SVG or transparent PNG, ideally 128×128 pixels or larger.
- Recommended background format: WebP or JPEG around 1920×1080 pixels.

Files are served only by the local dashboard under `/custom/`; no external icon service or account is required.
