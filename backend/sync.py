from gitlab_client import get_latest_commit, download_repo_archive
from file_manager import clear_folder, save_repo_archive


def sync_repo():
    """Sync repository from GitLab without clearing Neo4j database."""
    latest_commit = get_latest_commit()

    clear_folder()
    archive = download_repo_archive(latest_commit)
    save_repo_archive(archive)