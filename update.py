import sys
import requests
import json
from typing import List, Dict, Optional
import re
import os
import logging
import zipfile
import shutil
import argparse
import time
from datetime import datetime
from enum import Enum  # 确保导入 Enum

# PySide2 Imports
from PySide2.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QPushButton, QTextEdit, QProgressBar,
                               QMessageBox, QLabel, QFileDialog, QRadioButton,
                               QButtonGroup, QDialog, QVBoxLayout as QVLayout)
from PySide2.QtCore import Qt, Signal, QThread, QObject
from PySide2.QtGui import QTextCursor, QFont

THIS_VERSION = "v3.5"


# ==================== 枚举与配置 ====================

class VersionType(Enum):
    """版本类型枚举"""
    PYINSTALLER = "pyinstaller"
    NUITKA = "nuitka"


class UpdateConfig:
    """更新程序配置管理类"""
    CONFIG_FILE = "update_config.json"

    @staticmethod
    def load() -> dict:
        """加载配置文件"""
        default_config = {
            'version_type': VersionType.PYINSTALLER.value
        }

        if not os.path.exists(UpdateConfig.CONFIG_FILE):
            return default_config

        try:
            with open(UpdateConfig.CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                if 'version_type' not in config:
                    config['version_type'] = VersionType.PYINSTALLER.value
                return config
        except Exception:
            return default_config

    @staticmethod
    def save(config: dict):
        """保存配置文件"""
        try:
            with open(UpdateConfig.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置文件失败: {e}")


# ==================== 核心逻辑类 ====================

class UpdateChecker:
    """
    检查项目更新的类，逻辑与原版保持一致，但将I/O操作改为回调
    """

    def __init__(self, log_callback, progress_callback, debug_mode=False, mirror_only=False,
                 version_type=VersionType.PYINSTALLER):
        self.debug_mode = debug_mode
        self.mirror_only = mirror_only
        self.version_type = version_type
        self.log_callback = log_callback
        self.progress_callback = progress_callback

        if self.debug_mode:
            self.work_dir = "./debug"
            if not os.path.exists(self.work_dir):
                os.makedirs(self.work_dir)
        else:
            self.work_dir = "."

        self.gitee_api_url = "https://gitee.com/api/v5/repos/Bilibili-Supercmd/classroom_lottery/releases"
        self.github_api_url = "https://api.github.com/repos/trustedinster/classroom_lottery/releases"
        self.github_mirror_base = "https://gh.gh.supercmd.xin"

        self.headers = {
            'User-Agent': 'ClassroomLottery Update Checker'
        }

        self.setup_logging()

    def setup_logging(self):
        """设置日志记录"""
        log_dir = os.path.join(self.work_dir, 'logs')
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        log_file = os.path.join(log_dir, f'update_{datetime.now().strftime("%Y%m%d")}.log')
        logging.basicConfig(
            level=logging.DEBUG if self.debug_mode else logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
            ]
        )
        self.logger = logging.getLogger(__name__)

    def _log(self, msg):
        """统一日志输出方法"""
        if self.log_callback:
            self.log_callback(msg)
        self.logger.info(msg)

    def _compare_versions(self, version1: str, version2: str) -> int:
        """比较两个版本号"""
        v1 = version1.lstrip('v')
        v2 = version2.lstrip('v')
        nums1 = [int(x) for x in re.split(r'[.-]', v1) if x.isdigit()]
        nums2 = [int(x) for x in re.split(r'[.-]', v2) if x.isdigit()]
        max_len = max(len(nums1), len(nums2))
        nums1.extend([0] * (max_len - len(nums1)))
        nums2.extend([0] * (max_len - len(nums2)))
        for i in range(max_len):
            if nums1[i] > nums2[i]:
                return 1
            elif nums1[i] < nums2[i]:
                return -1
        return 0

    def get_gitee_releases(self) -> Optional[List[Dict]]:
        try:
            params = {'page': 1, 'per_page': 20, 'direction': 'asc'}
            response = requests.get(self.gitee_api_url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self._log(f"从Gitee获取更新信息失败: {e}")
            return None

    def get_github_releases(self) -> Optional[List[Dict]]:
        try:
            params = {'page': 1, 'per_page': 20, 'direction': 'desc'}
            response = requests.get(self.github_api_url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self._log(f"从GitHub获取更新信息失败: {e}")
            return None

    def get_all_releases(self) -> tuple:
        gitee_releases = self.get_gitee_releases()
        github_releases = self.get_github_releases()
        return gitee_releases, github_releases

    def get_best_update_source(self) -> Optional[Dict]:
        gitee_releases, github_releases = self.get_all_releases()
        best_source = None

        if gitee_releases:
            gitee_latest = self._find_latest_release(gitee_releases)
            if gitee_latest and 'tag_name' in gitee_latest:
                if self.is_newer_version(gitee_latest['tag_name']):
                    best_source = {'source': 'gitee', 'release': gitee_latest}

        if github_releases:
            github_latest = self._find_latest_release(github_releases)
            if github_latest and 'tag_name' in github_latest:
                if self.is_newer_version(github_latest['tag_name']):
                    if best_source is None or self._compare_versions(github_latest['tag_name'],
                                                                     best_source['release']['tag_name']) > 0:
                        best_source = {'source': 'github', 'release': github_latest}

        return best_source

    def _find_latest_release(self, releases: List[Dict]) -> Optional[Dict]:
        if not releases:
            return None
        stable_releases = [release for release in releases if not release.get('prerelease', False)]
        if not stable_releases:
            return None
        return stable_releases[0]

    def is_newer_version(self, latest_version: str) -> bool:
        return self._compare_versions(latest_version, THIS_VERSION) > 0

    def find_download_url(self, release: Dict, tag_name: str) -> Optional[str]:
        """
        查找下载链接，增加了回退逻辑以支持旧版文件名
        """
        if 'assets' not in release or not release['assets']:
            return None

        assets = release['assets']

        # 定义查找优先级的文件名列表
        possible_filenames = []

        if self.version_type == VersionType.NUITKA:
            possible_filenames.append(f"classroom_lottery_nuitka_{tag_name}.zip")
            # 如果找不到 Nuitka 版，不回退到 PyInstaller，返回 None
        else:
            possible_filenames.append(f"classroom_lottery_pyinstaller_{tag_name}.zip")
            # 回退1: 尝试旧版命名 (无后缀)
            possible_filenames.append(f"classroom_lottery_{tag_name}.zip")

        # 遍历资产进行匹配
        for expected_name in possible_filenames:
            for asset in assets:
                if 'browser_download_url' in asset and 'name' in asset:
                    if asset['name'] == expected_name:
                        return asset['browser_download_url']

        # 兜底：查找任何包含 classroom_lottery 的 zip 文件 (最后手段)
        for asset in assets:
            if 'browser_download_url' in asset and 'name' in asset:
                if 'classroom_lottery' in asset['name'] and '.zip' in asset['name']:
                    self._log(f"使用模糊匹配: {asset['name']}")
                    return asset['browser_download_url']

        return None

    def convert_to_mirror_url(self, url: str) -> str:
        if "github.com" in url:
            return url.replace("https://github.com", self.github_mirror_base)
        return url

    def download_with_progress(self, url: str, filename: str) -> bool:
        filepath = os.path.join(self.work_dir, filename)

        if self.mirror_only and "github.com" in url:
            self._log("使用镜像站下载...")
            url = self.convert_to_mirror_url(url)
            return self._perform_download(url, filepath, filename)

        self._log(f"开始下载: {filename}")
        success = self._perform_download(url, filepath, filename)

        if not success and "github.com" in url:
            self._log("尝试使用镜像站下载...")
            mirror_url = self.convert_to_mirror_url(url)
            success = self._perform_download(mirror_url, filepath, filename)

        return success

    def _perform_download(self, url: str, filepath: str, filename: str) -> bool:
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))

            with open(filepath, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        size = file.write(chunk)
                        if self.progress_callback:
                            current_pos = file.tell()
                            self.progress_callback(current_pos, total_size)

            self._log("下载完成!")
            return True
        except Exception as e:
            self._log(f"下载失败: {e}")
            return False

    def extract_and_install(self, zip_filename: str) -> bool:
        try:
            zip_filepath = os.path.join(self.work_dir, zip_filename)

            if not os.path.exists(zip_filepath):
                self._log(f"找不到文件: {zip_filename}")
                return False

            self._log(f"开始解压: {zip_filename}")

            temp_dir = os.path.join(self.work_dir, "temp_extract")
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            os.makedirs(temp_dir)

            with zipfile.ZipFile(zip_filepath, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

            self._log("解压完成，开始安装...")

            file_count = 0
            for root, dirs, files in os.walk(temp_dir):
                rel_path = os.path.relpath(root, temp_dir)
                dest_path = os.path.join(self.work_dir, rel_path) if rel_path != "." else self.work_dir

                if not os.path.exists(dest_path):
                    os.makedirs(dest_path)

                for file in files:
                    src_file = os.path.join(root, file)
                    dest_file = os.path.join(dest_path, file)

                    if self.debug_mode and file.endswith('.exe'):
                        py_file = file.replace('.exe', '.py')
                        py_src_file = os.path.join(os.path.dirname(src_file), py_file)
                        if os.path.exists(py_src_file):
                            shutil.copy2(py_src_file, dest_file.replace('.exe', '.py'))
                        else:
                            shutil.copy2(src_file, dest_file)
                    else:
                        shutil.copy2(src_file, dest_file)

                    file_count += 1
                    if file_count % 10 == 0 and self.progress_callback:
                        self.progress_callback(file_count, file_count)

            shutil.rmtree(temp_dir)
            self._log("安装完成!")
            return True
        except Exception as e:
            self._log(f"安装失败: {e}")
            return False


# ==================== GUI 组件 ====================

class VersionSelectDialog(QDialog):
    """版本选择对话框"""

    def __init__(self, parent=None, nuitka_available=True, pyinstaller_available=True):
        super().__init__(parent)
        self.setWindowTitle("选择更新版本")
        self.setModal(True)
        self.setFixedSize(400, 200)

        layout = QVLayout(self)

        title_label = QLabel("请选择要下载的版本：")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title_label)

        self.radio_pyinstaller = QRadioButton("PyInstaller 版本")
        self.radio_pyinstaller.setToolTip("传统打包方式，体积较小，兼容性好")
        layout.addWidget(self.radio_pyinstaller)

        self.radio_nuitka = QRadioButton("Nuitka 版本")
        self.radio_nuitka.setToolTip("Nuitka 编译方式，运行性能更好，启动更快")
        layout.addWidget(self.radio_nuitka)

        self.button_group = QButtonGroup(self)
        self.button_group.addButton(self.radio_pyinstaller)
        self.button_group.addButton(self.radio_nuitka)

        # 设置可用性
        if not nuitka_available:
            self.radio_nuitka.setEnabled(False)
            self.radio_nuitka.setText("Nuitka 版本 (此版本不可用)")
        if not pyinstaller_available:
            self.radio_pyinstaller.setEnabled(False)
            self.radio_pyinstaller.setText("PyInstaller 版本 (此版本不可用)")

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_ok = QPushButton("确定")
        self.btn_ok.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_ok)

        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        layout.addStretch()
        layout.addLayout(btn_layout)

        self.load_config()

    def load_config(self):
        config = UpdateConfig.load()
        version_type = config.get('version_type', VersionType.PYINSTALLER.value)

        if version_type == VersionType.NUITKA.value and self.radio_nuitka.isEnabled():
            self.radio_nuitka.setChecked(True)
        else:
            self.radio_pyinstaller.setChecked(True)

    def get_selected_version_type(self) -> VersionType:
        if self.radio_nuitka.isChecked():
            return VersionType.NUITKA
        else:
            return VersionType.PYINSTALLER

    def save_config(self):
        config = UpdateConfig.load()
        config['version_type'] = self.get_selected_version_type().value
        UpdateConfig.save(config)


class UpdateWorker(QThread):
    """后台工作线程"""
    log_signal = Signal(str)
    progress_signal = Signal(int, int)
    check_finished_signal = Signal(object)
    download_finished_signal = Signal(bool, str)
    install_finished_signal = Signal(bool)

    def __init__(self, checker=None):
        super().__init__()
        self.checker = checker
        self.task = None
        self.args = None

    def run_check(self):
        self.task = "check"
        self.start()

    def run_download(self, url, filename):
        self.args = (url, filename)
        self.task = "download"
        self.start()

    def run_install(self, filename):
        self.args = (filename,)
        self.task = "install"
        self.start()

    def run(self):
        if not self.checker:
            self.log_signal.emit("错误：更新核心组件未初始化！")
            return
        try:
            if self.task == "check":
                result = self.checker.get_best_update_source()
                self.check_finished_signal.emit(result)

            elif self.task == "download":
                url, filename = self.args
                success = self.checker.download_with_progress(url, filename)
                self.download_finished_signal.emit(success, filename)

            elif self.task == "install":
                filename, = self.args
                success = self.checker.extract_and_install(filename)
                self.install_finished_signal.emit(success)
        except Exception as e:
            self.log_signal.emit(f"任务执行出错: {e}")
            self.progress_signal.emit(0, 0)


class UpdateWindow(QMainWindow):
    def __init__(self, debug=False, mirror_only=False, auto_download=False, unzip_only=False):
        super().__init__()
        self.setWindowTitle(f"课堂抽号程序更新工具 v{THIS_VERSION}")
        self.resize(900, 600)

        self.debug_mode = debug
        self.mirror_only = mirror_only
        self.auto_download = auto_download
        self.unzip_only = unzip_only

        self.current_best_source = None
        self.current_filename = None

        config = UpdateConfig.load()
        self.version_type = VersionType(config.get('version_type', VersionType.PYINSTALLER.value))

        self.worker = UpdateWorker(checker=None)

        self.checker = UpdateChecker(
            log_callback=lambda msg: self.worker.log_signal.emit(msg),
            progress_callback=lambda cur, total: self.worker.progress_signal.emit(cur, total),
            debug_mode=self.debug_mode,
            mirror_only=self.mirror_only,
            version_type=self.version_type
        )

        self.worker.checker = self.checker
        self.connect_signals()
        self.init_ui()

        if self.unzip_only:
            self.handle_unzip_only()
        else:
            self.worker.run_check()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        btn_layout = QHBoxLayout()
        self.btn_check = QPushButton("检查更新")
        self.btn_check.clicked.connect(self.on_check_click)
        self.btn_check.setEnabled(False)

        self.btn_download = QPushButton("下载更新")
        self.btn_download.clicked.connect(self.start_download)
        self.btn_download.setEnabled(False)

        self.btn_install = QPushButton("安装更新")
        self.btn_install.clicked.connect(self.start_install)
        self.btn_install.setEnabled(False)

        self.btn_exit = QPushButton("退出")
        self.btn_exit.clicked.connect(self.close)

        btn_layout.addWidget(self.btn_check)
        btn_layout.addWidget(self.btn_download)
        btn_layout.addWidget(self.btn_install)
        btn_layout.addWidget(self.btn_exit)

        self.lbl_status = QLabel("正在初始化...")
        self.lbl_status.setStyleSheet("font-weight: bold; padding: 5px;")

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setAlignment(Qt.AlignCenter)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setStyleSheet("background-color: #1e1e1e; color: #00ff00;")

        main_layout.addLayout(btn_layout)
        main_layout.addWidget(self.lbl_status)
        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.log_text)

        self.connect_logger()

    def connect_logger(self):
        text_handler = logging.Handler()
        text_handler.emit = lambda record: self.log_text.append(f"{record.getMessage()}")
        logging.getLogger().addHandler(text_handler)

    def connect_signals(self):
        self.worker.log_signal.connect(self.append_log)
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.check_finished_signal.connect(self.on_check_finished)
        self.worker.download_finished_signal.connect(self.on_download_finished)
        self.worker.install_finished_signal.connect(self.on_install_finished)
        self.worker.started.connect(lambda: self.set_busy_state(True))
        self.worker.finished.connect(lambda: self.set_busy_state(False, task=self.worker.task))

    def append_log(self, msg):
        self.log_text.append(msg)
        sb = self.log_text.verticalScrollBar()
        sb.setValue(sb.maximum())

    def update_progress(self, current, total):
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
            percent = int((current / total) * 100)
            self.progress_bar.setFormat(f"{percent}%")
        else:
            self.progress_bar.setRange(0, 0)

    def set_busy_state(self, busy, task=None):
        if busy:
            self.progress_bar.setValue(0)
            self.btn_check.setEnabled(False)
            self.btn_download.setEnabled(False)
            self.btn_install.setEnabled(False)
        else:
            self.btn_check.setEnabled(True)
            if task == "check" and self.current_best_source:
                self.btn_download.setEnabled(True)
            elif task == "download" and self.current_filename:
                self.btn_install.setEnabled(True)

    def on_check_click(self):
        self.worker.run_check()

    def handle_unzip_only(self):
        work_dir = "./debug" if self.debug_mode else "."
        zip_files = []
        if os.path.exists(work_dir):
            for file in os.listdir(work_dir):
                if file.startswith("classroom_lottery_") and file.endswith(".zip"):
                    zip_files.append(file)

        if not zip_files:
            QMessageBox.warning(self, "错误", "未找到合法的zip文件")
            self.btn_check.setEnabled(True)
            return

        selected_file = zip_files[0]
        if len(zip_files) > 1:
            self.append_log(f"找到多个文件，默认选择: {selected_file}")

        self.current_filename = selected_file
        self.start_install()

    def start_download(self):
        if not self.current_best_source:
            return
        tag_name = self.current_best_source['release']['tag_name']
        download_url = self.checker.find_download_url(self.current_best_source['release'], tag_name)

        if download_url:
            version_suffix = "nuitka" if self.checker.version_type == VersionType.NUITKA else "pyinstaller"
            self.current_filename = f"classroom_lottery_{version_suffix}_{tag_name}.zip"
            self.lbl_status.setText(f"正在下载: {self.current_filename}")
            self.worker.run_download(download_url, self.current_filename)
        else:
            QMessageBox.warning(self, "错误", "未找到合适的下载链接，可能是该版本不包含所选构建类型。")

    def start_install(self):
        if not self.current_filename:
            return

        if not self.debug_mode and os.path.exists("update.exe"):
            reply = QMessageBox.question(
                self, '确认安装',
                "即将启动自我更新流程。\n程序将复制 update.exe 为 update_old.exe 并运行安装。\n完成后请手动重新启动程序。\n\n是否继续?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                try:
                    shutil.copy2("update.exe", "update_old.exe")
                    self.append_log("已复制 update.exe 为 update_old.exe")
                    import subprocess
                    subprocess.Popen(["update_old.exe", "--unzip-only"])
                    self.append_log("已启动更新安装程序，主程序即将退出。")
                    QTimer.singleShot(2000, QApplication.quit)
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"启动更新失败: {e}")
            else:
                self.worker.run_install(self.current_filename)
        else:
            self.worker.run_install(self.current_filename)

    def on_check_finished(self, best_source):
        if best_source:
            self.current_best_source = best_source
            release = best_source['release']
            tag_name = release['tag_name']

            self.append_log(f"发现新版本: {tag_name}")

            # 检测可用性：遍历 assets 查看是否有 nuitka 或 pyinstaller 关键字
            assets = release.get('assets', [])
            asset_names = [a.get('name', '') for a in assets]

            has_nuitka = any('nuitka' in name.lower() for name in asset_names)
            has_pyinstaller = any('pyinstaller' in name.lower() for name in asset_names)

            # 兼容旧版：如果没有 pyinstaller 后缀，但有默认的 classroom_lottery_tag.zip
            # 我们将其视为 pyinstaller 可用
            has_legacy = any(f'classroom_lottery_{tag_name}.zip' == name for name in asset_names)

            if not has_pyinstaller and has_legacy:
                has_pyinstaller = True

            # 决策逻辑
            target_type = VersionType.PYINSTALLER

            if has_nuitka and has_pyinstaller:
                # 新版：两者都有，弹出选择框
                self.append_log("检测到新版发布，支持 PyInstaller 和 Nuitka 两个版本。")
                dialog = VersionSelectDialog(self, nuitka_available=True, pyinstaller_available=True)
                result = dialog.exec_()

                if result == QDialog.Accepted:
                    dialog.save_config()
                    target_type = dialog.get_selected_version_type()
                    self.checker.version_type = target_type
                    self.append_log(f"用户选择: {target_type.value} 版本")
                    self.btn_download.setEnabled(True)
                else:
                    self.append_log("用户取消下载")
            else:
                # 旧版或不完整情况
                if has_nuitka:
                    self.append_log("仅检测到 Nuitka 版本可用。")
                    target_type = VersionType.NUITKA
                elif has_pyinstaller:
                    self.append_log("检测到旧版版本（或仅 PyInstaller 版），将下载 PyInstaller 版本。")
                    target_type = VersionType.PYINSTALLER
                else:
                    # 兜底，找不到任何特定文件
                    self.append_log("未检测到特定版本标识，尝试默认下载。")
                    target_type = VersionType.PYINSTALLER

                self.checker.version_type = target_type
                self.btn_download.setEnabled(True)

            if 'body' in release and release['body']:
                self.append_log("更新内容:\n" + release['body'])

            if self.auto_download:
                self.start_download()
        else:
            self.lbl_status.setText("当前已是最新版本")
            self.append_log("当前已是最新版本")

    def on_download_finished(self, success, filename):
        if success:
            self.lbl_status.setText("下载完成")
            self.append_log(f"文件已保存为: {filename}")
            self.btn_install.setEnabled(True)
        else:
            self.lbl_status.setText("下载失败")
            QMessageBox.warning(self, "下载失败", "请查看日志获取详细信息。")

    def on_install_finished(self, success):
        if success:
            self.lbl_status.setText("安装完成")
            self.append_log("安装完成!")
            QMessageBox.information(self, "完成", "更新安装成功！\n请重新运行程序。")
        else:
            self.lbl_status.setText("安装失败")
            QMessageBox.critical(self, "安装失败", "请查看日志获取详细信息。")


from PySide2.QtCore import QTimer


def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)

    parser = argparse.ArgumentParser(description="课堂抽号程序更新工具 (GUI版)")
    parser.add_argument('-y', '--auto-download', action='store_true', help="自动下载，无需确认")
    parser.add_argument('--unzip-only', action='store_true', help="仅解压目录下已有的合法zip文件")
    parser.add_argument('--debug', action='store_true', help="调试模式，工作目录为./debug")
    parser.add_argument('--mirror-only', action='store_true', help="优先使用镜像站下载GitHub资源")
    parser.add_argument('--version-type', choices=['pyinstaller', 'nuitka'], default=None,
                        help="指定版本类型 (pyinstaller/nuitka)，如未指定则弹窗选择或使用配置文件")

    args, unknown = parser.parse_known_args()

    version_type = None
    if args.version_type:
        if args.version_type == 'nuitka':
            version_type = VersionType.NUITKA
        else:
            version_type = VersionType.PYINSTALLER

    if version_type:
        config = UpdateConfig.load()
        config['version_type'] = version_type.value
        UpdateConfig.save(config)

    window = UpdateWindow(
        debug=args.debug,
        mirror_only=args.mirror_only,
        auto_download=args.auto_download,
        unzip_only=args.unzip_only
    )
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()