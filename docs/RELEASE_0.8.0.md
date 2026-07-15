# Rogue Dashboard 0.8.0

Version 0.8.0 makes larger installations easier to organise and move.

## Highlights

- Create up to 20 named pages from **Customise → Layout**.
- Page tabs are responsive, keyboard-focusable and available without signing in.
- Groups and newly discovered Docker cards stay attached to their selected page.
- Deleting a populated page requires confirmation and removes only that page's groups.
- JSON backups exported by Rogue Dashboard can now be validated and restored during first setup or through **Customise → Connect**.
- Existing 0.7 and earlier dashboards migrate into a single `Home` page without losing or reordering cards.

## Upgrade

Keep `.env`, `data/` and `custom/`, replace repository-controlled files and run `./upgrade.sh`. Dashboard schema 5 migrates to schema 6 automatically; the SQLite table structure remains compatible.
