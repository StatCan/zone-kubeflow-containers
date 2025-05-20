import re
import os
import requests
import subprocess
import datetime

# Configuration - MODIFY THESE AS NEEDED
DOCKERFILE_PATH = "images/mid/Dockerfile"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO_OWNER = "StatCan"
REPO_NAME = "zone-kubeflow-containers"
GIT_EMAIL = "your_bot_email@example.com"  # Set a bot email for commit
GIT_USERNAME = "YourUpdateBot"  # Set a bot username for commit
BRANCH_NAME = f"update-vscode-extensions-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"


def extract_extensions_and_vsix(dockerfile_path):
    extensions = []
    vsix_files = []
    github_vsix = []
    with open(dockerfile_path, "r") as f:
        for line in f:
            match = re.search(
                r"code-server\s+--install-extension\s+([^\s@\\]+)(?:@([^\s\\]+))?", line
            )
            if match:
                ext = match.group(1)
                version = match.group(2)
                if ext.endswith(".vsix"):
                    vsix_files.append(ext)
                else:
                    extensions.append({"id": ext, "version": version})
            # Look for wget lines for vsix
            wget_match = re.search(
                r"wget.*github\.com/([^/]+/[^/]+)/releases/download/v?([0-9.]+)/([^\s]+\.vsix)", line
            )
            if wget_match:
                repo = wget_match.group(1)
                version = wget_match.group(2)
                vsix_name = wget_match.group(3)
                github_vsix.append({"repo": repo, "version": version, "file": vsix_name})
    return extensions, vsix_files, github_vsix

def get_latest_openvsx_version(ext_id):
    try:
        namespace, name = ext_id.split('.', 1)
        url = f"https://open-vsx.org/api/{namespace}/{name}/latest"
        resp = requests.get(url)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("version")
    except Exception as e:
        print(f"Error fetching {ext_id}: {e}")
    return None

def get_latest_github_release(repo):
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    resp = requests.get(url)
    if resp.status_code == 200:
        data = resp.json()
        return data['tag_name'].lstrip('v')
    return None

def update_dockerfile(ext_id, old_version, new_version):
    # Use sed to replace the version in the Dockerfile
    escaped_ext_id = ext_id.replace(".", "\\.")  # Escape dots for sed
    sed_command = f"sed -i 's/code-server --install-extension {escaped_ext_id}@{old_version}/code-server --install-extension {escaped_ext_id}@{new_version}/g' {DOCKERFILE_PATH}"
    try:
        subprocess.run(sed_command, shell=True, check=True)
        print(f"Updated {ext_id} from {old_version} to {new_version}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error updating {ext_id}: {e}")
        return False

def create_github_pull_request(outdated_extensions):
    if not outdated_extensions:
        print("No updates to commit.")
        return

    # Configure Git
    subprocess.run(["git", "config", "user.email", GIT_EMAIL], check=True)
    subprocess.run(["git", "config", "user.name", GIT_USERNAME], check=True)

    # Create a new branch
    try:
        subprocess.run(["git", "checkout", "-b", BRANCH_NAME], check=True)
    except subprocess.CalledProcessError:
        print(f"Branch {BRANCH_NAME} already exists.  Please delete it, or check it out to continue...")
        return

    # Commit the changes
    subprocess.run(["git", "add", DOCKERFILE_PATH], check=True)
    commit_message = "Update VSCode extensions in Dockerfile:\n"
    for ext in outdated_extensions:
        commit_message += f"- {ext['id']}: {ext['old_version']} -> {ext['new_version']}\n"
    subprocess.run(["git", "commit", "-m", commit_message], check=True)

    # Push the branch
    subprocess.run(["git", "push", "origin", BRANCH_NAME], check=True)

    # Create the pull request
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/pulls"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    payload = {
        "title": "Automated: Update VSCode Extensions",
        "head": BRANCH_NAME,
        "base": "main",  # Or your main branch name
        "body": commit_message
    }
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 201:
        print(f"Pull request created: {response.json().get('html_url')}")
    else:
        print(f"Failed to create pull request: {response.status_code}, {response.text}")

# Main logic
extensions, vsix_files, github_vsix = extract_extensions_and_vsix(DOCKERFILE_PATH)

outdated_extensions = []

print("Checking Marketplace Extensions:")
for ext in extensions:
    latest = get_latest_openvsx_version(ext['id'])
    if latest and ext['version'] and latest != ext['version']:
        print(f"  - {ext['id']}@{ext['version']} (latest: {latest})  <-- UPDATE AVAILABLE")
        if update_dockerfile(ext['id'], ext['version'], latest):
            outdated_extensions.append({"id": ext['id'], "old_version": ext['version'], "new_version": latest})
    else:
        print(f"  - {ext['id']}@{ext['version']} (latest: {latest or 'unknown'})")

print("\nGitHub .vsix downloads:")
for gvsix in github_vsix:
    latest = get_latest_github_release(gvsix['repo'])
    if latest and gvsix['version'] and latest != gvsix['version']:
        print(f"  - {gvsix['repo']} {gvsix['file']} (current: {gvsix['version']}, latest: {latest})  <-- UPDATE AVAILABLE")
        vsix_id = gvsix['file'].replace(".vsix", "") #Strip .vsix from the name
        if update_dockerfile(vsix_id, gvsix['version'], latest):
            outdated_extensions.append({"id": gvsix['file'], "old_version": gvsix['version'], "new_version": latest})
    else:
        print(f"  - {gvsix['repo']} {gvsix['file']} (current: {gvsix['version']}, latest: {latest or 'unknown'})")

create_github_pull_request(outdated_extensions)
