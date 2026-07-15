# Migration policy

Rogue Dashboard migrations are forward-only, automatic and backup-first. The upgrade script stops briefly to copy `.env`, `data/` and `custom/` before replacing the image.

## Supported release path

| From | To | Automatic changes |
| --- | --- | --- |
| 0.6.x | 0.7.x | No database change; Docker metrics and optional backup retention become available. |
| 0.7.x | 0.8.x | Dashboard schema 6 creates a Home page and assigns existing groups to it. |
| 0.8.x | 1.0.x | Session timestamps and the bounded action-audit table are added in place. |
| 0.6.x or newer | 1.0.x | All intermediate migrations are applied during validation/startup. |

The persistent contract is:

- `.env` keeps runtime settings and credentials;
- `data/` keeps SQLite state;
- `custom/` keeps operator-provided images;
- repository-controlled application and Compose files are replaceable.

Downgrading across a schema change is not guaranteed. Restore the timestamped backup created before that upgrade when returning to an older major/minor release.

Dashboard JSON restores are validated and never contain `.env` credential values. A JSON export does not replace a full backup because it excludes administrator accounts, sessions and action history.
