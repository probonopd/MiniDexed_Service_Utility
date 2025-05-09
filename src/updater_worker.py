from PyQt6.QtCore import QThread, pyqtSignal
import os, sys, tempfile, zipfile, requests, ftplib, socket, time, re
from zeroconf import ServiceBrowser, ServiceListener, Zeroconf

class UpdaterWorker(QThread):
    status = pyqtSignal(str)
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)  # success, message
    device_list = pyqtSignal(list)

    def __init__(self, release_type, pr_number, device_ip, update_performances, github_token=None, src_path=None):
        super().__init__()
        self.release_type = release_type
        self.pr_number = pr_number
        self.device_ip = device_ip
        self.update_performances = update_performances
        self.github_token = github_token
        self.src_path = src_path
        self._stop = False

    def run(self):
        ftp = None
        try:
            self.status.emit("Starting update...")
            # --- Download release logic ---
            if self.release_type == 0:  # Latest
                self.status.emit("Downloading latest official release...")
                zip_path = self.download_latest_release_github_api('latest')
            elif self.release_type == 1:  # Continuous
                self.status.emit("Downloading continuous build...")
                zip_path = self.download_latest_release_github_api('continuous')
            elif self.release_type == 2:  # Local build (from src/)
                self.status.emit("Using local build from src/ directory...")
                zip_path = None
                extract_path = self.src_path or os.path.join(os.path.dirname(__file__), 'src')
            elif self.release_type == 3:  # PR build
                self.status.emit("Downloading PR build artifact...")
                zip_path = self.download_pr_artifact(self.pr_number)
                if not zip_path:
                    self.finished.emit(False, "Failed to download PR artifact.")
                    return
            else:
                self.status.emit("Unknown release type.")
                self.finished.emit(False, "Unknown release type.")
                return
            if self.release_type in (0, 1, 3):
                if not zip_path:
                    self.finished.emit(False, "Failed to download release.")
                    return
                self.status.emit("Extracting release...")
                extract_path = self.extract_zip(zip_path)
            # --- FTP upload logic ---
            self.status.emit(f"Connecting to {self.device_ip} ...")
            ftp = ftplib.FTP()
            ftp.connect(self.device_ip, 21, timeout=10)
            ftp.login("admin", "admin")
            ftp.set_pasv(True)
            self.status.emit(f"Connected to {self.device_ip} (passive mode). Uploading kernel images...")
            # Find kernel*.img files
            kernel_files = []
            for root, dirs, files in os.walk(extract_path):
                for file in files:
                    if file.startswith("kernel") and file.endswith(".img"):
                        kernel_files.append(os.path.join(root, file))
            total = len(kernel_files)
            uploaded_files = []
            for idx, local_path in enumerate(kernel_files):
                file = os.path.basename(local_path)
                remote_path_new = f"/SD/{file}.new"
                remote_path_final = f"/SD/{file}"
                filesize = os.path.getsize(local_path)
                uploaded = [0]
                self.status.emit(f"Uploading {file} as {file}.new to {self.device_ip}...")
                def progress_callback(data):
                    uploaded[0] += len(data)
                    percent = int(((idx + uploaded[0]/filesize) / total) * 100)
                    self.progress.emit(percent)
                with open(local_path, 'rb') as f:
                    ftp.storbinary(f'STOR {remote_path_new}', f, 8192, callback=progress_callback)
                self.status.emit(f"Uploaded {file} as {file}.new to {self.device_ip}.")
                # Atomically replace old file with new one
                try:
                    try:
                        ftp.delete(remote_path_final)
                    except Exception:
                        pass
                    ftp.rename(remote_path_new, remote_path_final)
                    self.status.emit(f"Renamed {file}.new to {file} on device.")
                except Exception as e:
                    self.status.emit(f"[WARN] Could not rename {remote_path_new} to {remote_path_final}: {e}")
            # --- Performances update logic ---
            if self.update_performances:
                self.status.emit("Updating Performances: recursively deleting and uploading /SD/performance directory...")
                def ftp_rmdirs(ftp, path):
                    try:
                        items = ftp.nlst(path)
                    except Exception as e:
                        self.status.emit(f"[WARN] Could not list {path}: {e}")
                        return
                    for item in items:
                        if item in ['.', '..', path]:
                            continue
                        full_path = f"{path}/{item}" if not item.startswith(path) else item
                        try:
                            ftp.delete(full_path)
                            self.status.emit(f"Deleted file: {full_path}")
                        except Exception:
                            try:
                                ftp_rmdirs(ftp, full_path)
                                ftp.rmd(full_path)
                                self.status.emit(f"Deleted directory: {full_path}")
                            except Exception as e:
                                self.status.emit(f"[WARN] Could not delete {full_path}: {e}")
                try:
                    ftp_rmdirs(ftp, '/SD/performance')
                    try:
                        ftp.rmd('/SD/performance')
                        self.status.emit("Deleted /SD/performance on device.")
                    except Exception as e:
                        self.status.emit(f"[WARN] Could not delete /SD/performance directory itself: {e}")
                except Exception as e:
                    self.status.emit(f"Warning: Could not delete /SD/performance: {e}")
                # Upload extracted performance/ recursively
                local_perf = os.path.join(extract_path, 'performance')
                def ftp_mkdirs(ftp, path):
                    try:
                        ftp.mkd(path)
                    except Exception:
                        pass
                def ftp_upload_dir(ftp, local_dir, remote_dir):
                    ftp_mkdirs(ftp, remote_dir)
                    for item in os.listdir(local_dir):
                        lpath = os.path.join(local_dir, item)
                        rpath = f"{remote_dir}/{item}"
                        if os.path.isdir(lpath):
                            ftp_upload_dir(ftp, lpath, rpath)
                        else:
                            with open(lpath, 'rb') as fobj:
                                ftp.storbinary(f'STOR {rpath}', fobj)
                            self.status.emit(f"Uploaded {rpath}")
                if os.path.isdir(local_perf):
                    ftp_upload_dir(ftp, local_perf, '/SD/performance')
                    self.status.emit("Uploaded new /SD/performance directory.")
                else:
                    self.status.emit("No extracted performance/ directory found, skipping upload.")
                # Upload performance.ini if it exists in extract_path
                local_perfini = os.path.join(extract_path, 'performance.ini')
                if os.path.isfile(local_perfini):
                    with open(local_perfini, 'rb') as fobj:
                        ftp.storbinary('STOR /SD/performance.ini', fobj)
                    self.status.emit("Uploaded /SD/performance.ini.")
                else:
                    self.status.emit("No extracted performance.ini found, skipping upload.")
            try:
                ftp.sendcmd("BYE")
            except Exception:
                pass
            self.status.emit(f"Disconnected from {self.device_ip}.")
            self.progress.emit(100)
            self.finished.emit(True, "Update finished successfully.")
        except Exception as e:
            if ftp is not None:
                try:
                    ftp.close()
                except Exception:
                    pass
            import sys
            print(f"Error: {e}", file=sys.stderr)
            self.status.emit(f"Error: {e}")
            self.finished.emit(False, str(e))
        finally:
            if ftp is not None:
                try:
                    ftp.close()
                except Exception:
                    pass

    def download_latest_release_github_api(self, release_type):
        headers = {'Accept': 'application/vnd.github.v3+json'}
        repo = 'probonopd/MiniDexed'
        if release_type == 'latest':
            api_url = f'https://api.github.com/repos/{repo}/releases/latest'
            resp = requests.get(api_url, headers=headers)
            if resp.status_code != 200:
                self.status.emit(f"GitHub API error: {resp.status_code}")
                return None
            release = resp.json()
            assets = release.get('assets', [])
        elif release_type == 'continuous':
            api_url = f'https://api.github.com/repos/{repo}/releases'
            resp = requests.get(api_url, headers=headers)
            if resp.status_code != 200:
                self.status.emit(f"GitHub API error: {resp.status_code}")
                return None
            releases = resp.json()
            release = next((r for r in releases if 'continuous' in (r.get('tag_name','')+r.get('name','')).lower()), None)
            if not release:
                self.status.emit("No continuous release found.")
                return None
            assets = release.get('assets', [])
        else:
            self.status.emit(f"Unknown release type: {release_type}")
            return None
        asset = next((a for a in assets if a['name'].startswith('MiniDexed') and a['name'].endswith('.zip')), None)
        if not asset:
            self.status.emit("No MiniDexed*.zip asset found in release.")
            return None
        url = asset['browser_download_url']
        self.status.emit(f"Downloading asset: {asset['name']} from {url}")
        headers = {"User-Agent": "MiniDexed-Updater"}
        github_token = self.github_token or os.environ.get("GITHUB_TOKEN")
        if github_token:
            headers["Authorization"] = f"Bearer {github_token}"
        resp = requests.get(url, stream=True, headers=headers)
        if resp.status_code == 200:
            zip_path = os.path.join(tempfile.gettempdir(), asset['name'])
            with open(zip_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            return zip_path
        self.status.emit(f"Failed to download asset: {resp.status_code}")
        return None

    def extract_zip(self, zip_path):
        extract_path = os.path.join(tempfile.gettempdir(), "MiniDexed")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)
        return extract_path

    def download_pr_artifact(self, pr_number):
        import requests, re, tempfile, os
        repo = 'probonopd/MiniDexed'
        github_token = self.github_token or os.environ.get("GITHUB_TOKEN")
        pr_input = pr_number.strip()
        m = re.search(r'(\d+)$', pr_input)
        if not m:
            self.status.emit(f"Could not parse PR number from: {pr_input}")
            return None
        pr_number = m.group(1)
        pr_url = f"https://github.com/{repo}/pull/{pr_number}"
        self.status.emit(f"Fetching PR page: {pr_url}")
        session = requests.Session()
        headers = {"User-Agent": "MiniDexed-Updater"}
        headers["Authorization"] = f"Bearer {github_token}"
        resp = session.get(pr_url, headers=headers)
        if resp.status_code != 200:
            self.status.emit(f"Failed to fetch PR page: {resp.status_code}")
            return None
        html = resp.text
        pattern = re.compile(r'<p dir="auto">Build for testing:(.*?)Use at your own risk\.', re.DOTALL)
        matches = pattern.findall(html)
        if not matches:
            self.status.emit("No build artifact links found in PR comment.")
            return None
        last_block = matches[-1]
        link_pattern = re.compile(r'<a href="([^"]+)">([^<]+)</a>')
        links = link_pattern.findall(last_block)
        if not links:
            self.status.emit("No artifact links found in PR comment block. Please ensure the PR contains a 'Build for testing' artifact and that your GitHub token is valid and has access.")
            return None
        url, name = links[0]
        self.status.emit(f"Downloading artifact: {name} from {url}")
        # Always use the token for artifact download, even if direct link
        artifact_headers = headers.copy()
        # If the link is a github.com link with /artifacts/{id}, use the API endpoint
        artifact_id_match = re.search(r'/artifacts/(\d+)', url)
        if artifact_id_match:
            artifact_id = artifact_id_match.group(1)
            api_url = f"https://api.github.com/repos/{repo}/actions/artifacts/{artifact_id}/zip"
            artifact_headers = {
                "User-Agent": "MiniDexed-Updater",
                "Accept": "application/vnd.github+json"
            }
            if github_token:
                artifact_headers["Authorization"] = f"Bearer {github_token}"
            resp = session.get(api_url, stream=True, headers=artifact_headers)
            print(f"[HTTP REQUEST] {resp.request.method} {resp.request.url}")
            print(f"[HTTP REQUEST HEADERS] {dict(resp.request.headers)}")
        else:
            # Fallback: direct link, do not use token headers
            resp = session.get(url, stream=True, headers=headers)
            print(f"[HTTP REQUEST] {resp.request.method} {resp.request.url}")
            print(f"[HTTP REQUEST HEADERS] {dict(resp.request.headers)}")
        if resp.status_code == 200:
            zip_path = os.path.join(tempfile.gettempdir(), name + ".zip")
            with open(zip_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            return zip_path
        self.status.emit(
            f"Failed to download artifact: HTTP status code {resp.status_code}.\n"
            "Possible reasons include:\n"
            "- The GitHub token is missing, invalid, or does not have access to the repository.\n"
            "- The artifact has expired (GitHub Actions artifacts are only available for a limited time).\n"
            "- The PR does not contain a 'Build for testing' artifact.\n"
            "- The repository or artifact is private and your token does not have sufficient permissions.\n"
            "- There is a network or GitHub outage.\n"
            "Please check your GitHub token in Preferences, verify the PR and its artifacts, and try again."
        )
        self.finished.emit(False, f"Failed to download PR artifact (HTTP {resp.status_code}).")
        return None

class DeviceDiscoveryWorker(QThread):
    device_found = pyqtSignal(str, str)  # name, ip
    finished = pyqtSignal()

    def __init__(self, service="_ftp._tcp.local.", timeout=7):
        super().__init__()
        self.service = service
        self.timeout = timeout
        self._stop = False

    def run(self):
        zeroconf = Zeroconf()
        ip_list = []
        name_list = []
        class MyListener(ServiceListener):
            def add_service(self, zc, type_, name):
                info = zc.get_service_info(type_, name)
                if info and info.addresses:
                    txt_records = info.properties
                    found = False
                    if txt_records:
                        for k, v in txt_records.items():
                            val = v.decode() if isinstance(v, bytes) else v
                            if (b"MiniDexed" in k or b"MiniDexed" in v) or ("MiniDexed" in str(k) or "MiniDexed" in str(val)):
                                found = True
                                break
                    if found:
                        ip = socket.inet_ntoa(info.addresses[0])
                        name = info.server.rstrip('.')
                        if ip not in ip_list:
                            ip_list.append(ip)
                            name_list.append(name)
                            self_outer.device_found.emit(name, ip)
        self_outer = self
        listener = MyListener()
        browser = ServiceBrowser(zeroconf, self.service, listener)
        self.msleep(int(self.timeout * 1000))
        zeroconf.close()
        self.finished.emit()
