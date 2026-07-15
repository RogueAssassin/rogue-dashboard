# Your custom artwork

Rogue Dashboard serves this folder at `/custom/` and mounts it read-only inside the container. Files placed here stay on the host when images are upgraded.

## Add a service icon

1. Copy a square SVG, PNG or WebP file into `custom/icons/`.
2. Open **Customise** and edit the service card.
3. Set **Icon URL or local path** to `/custom/icons/my-service.svg`.
4. Save the dashboard.

SVG is recommended for sharp results at every display size. For raster artwork, use a transparent square image of at least 128×128 pixels. Keep filenames simple, lowercase and free of spaces. Supported files are AVIF, GIF, ICO, JPEG, PNG, SVG and WebP, with a 10 MB limit per file.

## Add a background

1. Copy a WebP, JPEG or PNG file into `custom/backgrounds/`.
2. Open **Customise → Appearance**.
3. Enter `/custom/backgrounds/my-background.webp` in the background field.
4. Choose **Custom image** and save.

A 1920×1080 WebP image is a good balance between quality and load time.

## Container permissions

If a file does not appear, confirm that it is readable by the user configured as `PUID` and `PGID` in `.env`:

```bash
chmod 755 custom custom/icons custom/backgrounds
chmod 644 custom/icons/* custom/backgrounds/*
```

Do not store passwords, API keys or private configuration in this directory. Everything under `/custom/` is available to authenticated and unauthenticated dashboard visitors.
