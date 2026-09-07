"""
Module to control the perm deletion of trashed items past the retention window.
Trashing only sets deleted_at. This module is what actually reclaims disk
space, and it is the piece that makes the 30-day promise true.
"""

DEFAULT_RETENTION_DAYS = 30


def purge_trash(db, storage, cutoff_days: int = DEFAULT_RETENTION_DAYS, dry_run: bool = False) -> dict:
    """Delete files and folders trashed more than cutoff_days ago.

    Blobs are removed from disk *before* their database rows. That order
    matters: if the process dies midway, a surviving row with a missing blob
    is retried harmlessly on the next sweep, whereas a deleted row with a
    surviving blob leaves bytes on the disk that nothing knows about and
    nothing will ever reclaim.

    Pass dry_run=True to see what would go without touching anything.
    """
    summary = {
        "cutoff_days": cutoff_days,
        "dry_run": dry_run,
        "files_deleted": 0,
        "files_failed": 0,
        "folders_deleted": 0,
        "folders_failed": 0,
    }

    for row in db.get_expired_files(cutoff_days):
        file_id = row["file_id"]
        user_id = row["user_id"]
        file_uid = row["file_uid"]

        if dry_run:
            print(f"[dry run] would delete file {file_id} ({file_uid}) for user {user_id}")
            summary["files_deleted"] += 1
            continue

        if not storage.delete_file(user_id, file_uid):
            summary["files_failed"] += 1
            continue

        if db.permanently_delete_file(file_id):
            summary["files_deleted"] += 1
        else:
            summary["files_failed"] += 1

    for row in db.get_expired_folders(cutoff_days):
        folder_id = row["folder_id"]

        if dry_run:
            print(f"[dry run] would delete folder {folder_id}")
            summary["folders_deleted"] += 1
            continue

        if db.permanently_delete_folder(folder_id):
            summary["folders_deleted"] += 1
        else:
            summary["folders_failed"] += 1

    return summary