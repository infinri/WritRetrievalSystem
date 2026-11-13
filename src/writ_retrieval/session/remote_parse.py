def normalize_path(path: str) -> str:
    """Repo-root-relative normalization shared by diffstat and FileChange paths.

    Strips a single leading './' then a single leading '/', with no case folding.
    Applied IDENTICALLY to a diffstat path and a FileChange path before the
    IN-list lookup so the join cannot silently miss (a './x' diffstat path vs an
    'x' FileChange path).
    """
    if path.startswith("./"):
        path = path[2:]
    if path.startswith("/"):
        path = path[1:]
    return path
