import re
import requests

DOCKERFILE_PATH = "images/mid/Dockerfile"

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

# Main logic
extensions, vsix_files, github_vsix = extract_extensions_and_vsix(DOCKERFILE_PATH)

print("Marketplace Extensions:")
for ext in extensions:
    latest = get_latest_openvsx_version(ext['id'])
    if latest and ext['version'] and latest != ext['version']:
        print(f"  - {ext['id']}@{ext['version']} (latest: {latest})  <-- UPDATE AVAILABLE")
    else:
        print(f"  - {ext['id']}@{ext['version']} (latest: {latest or 'unknown'})")

print("\nExtensions installed from .vsix files (manual check required):")
for vsix in vsix_files:
    print(f"  - {vsix}")

print("\nGitHub .vsix downloads:")
for gvsix in github_vsix:
    latest = get_latest_github_release(gvsix['repo'])
    if latest and gvsix['version'] and latest != gvsix['version']:
        print(f"  - {gvsix['repo']} {gvsix['file']} (current: {gvsix['version']}, latest: {latest})  <-- UPDATE AVAILABLE")
    else:
        print(f"  - {gvsix['repo']} {gvsix['file']} (current: {gvsix['version']}, latest: {latest or 'unknown'})")
