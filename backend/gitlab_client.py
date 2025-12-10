import requests
from config import GITLAB_URL, GITLAB_PROJECT_ID, GITLAB_PRIVATE_TOKEN

HEADERS = {"PRIVATE-TOKEN": GITLAB_PRIVATE_TOKEN}

def get_latest_commit():
    url = f"{GITLAB_URL}/projects/{GITLAB_PROJECT_ID}/repository/commits"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.json()[0]["id"]

def download_repo_archive(commit_sha):
    url = f"{GITLAB_URL}/projects/{GITLAB_PROJECT_ID}/repository/archive.zip?sha={commit_sha}"
    response = requests.get(url, headers=HEADERS, stream=True)
    response.raise_for_status()
    return response.content
