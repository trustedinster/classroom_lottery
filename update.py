import requests
import json
import sys
from typing import List, Dict, Optional
import re
import os
import logging
import zipfile
import shutil
import argparse
import time
from datetime import datetime
from tqdm import tqdm

THIS_VERSION = "v3.4"

class UpdateChecker:
    """
    检查项目更新的类，支持从Gitee和GitHub获取发布信息
    """
    
    def __init__(self, debug_mode=False, mirror_only=False):
        # 设置工作目录
        self.debug_mode = debug_mode
        self.mirror_only = mirror_only
        if self.debug_mode:
            self.work_dir = "./debug"
            if not os.path.exists(self.work_dir):
                os.makedirs(self.work_dir)
        else:
            self.work_dir = "."
            
        # Gitee API地址（优先尝试）
        self.gitee_api_url = "https://gitee.com/api/v5/repos/Bilibili-Supercmd/classroom_lottery/releases"
        # GitHub API地址
        self.github_api_url = "https://api.github.com/repos/trustedinster/classroom_lottery/releases"
        
        # GitHub镜像站基础URL
        self.github_mirror_base = "https://gh.gh.supercmd.xin"
        
        # 请求头，用于GitHub API
        self.headers = {
            'User-Agent': 'ClassroomLottery Update Checker'
        }
        
        # 设置日志
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
    
    def _compare_versions(self, version1: str, version2: str) -> int:
        """
        比较两个版本号
        
        Args:
            version1: 版本号1
            version2: 版本号2
            
        Returns:
            int: 如果version1 > version2返回1，相等返回0，小于返回-1
        """
        # 移除可能存在的前缀'v'
        v1 = version1.lstrip('v')
        v2 = version2.lstrip('v')
        
        # 使用正则表达式提取版本号中的数字部分
        nums1 = [int(x) for x in re.split(r'[.-]', v1)]
        nums2 = [int(x) for x in re.split(r'[.-]', v2)]
        
        # 补齐长度，缺少的部分用0填充
        max_len = max(len(nums1), len(nums2))
        nums1.extend([0] * (max_len - len(nums1)))
        nums2.extend([0] * (max_len - len(nums2)))
        
        # 逐个比较版本号的每个部分
        for i in range(max_len):
            if nums1[i] > nums2[i]:
                return 1
            elif nums1[i] < nums2[i]:
                return -1
        return 0
    
    def get_gitee_releases(self) -> Optional[List[Dict]]:
        """
        从Gitee获取发布信息
        
        Returns:
            Optional[List[Dict]]: 发布信息列表或None（如果失败）
        """
        try:
            params = {
                'page': 1,
                'per_page': 20,
                'direction': 'desc'
            }
            response = requests.get(self.gitee_api_url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"从Gitee获取更新信息失败: {e}")
            self.logger.error(f"从Gitee获取更新信息失败: {e}")
            return None
    
    def get_github_releases(self) -> Optional[List[Dict]]:
        """
        从GitHub获取发布信息
        
        Returns:
            Optional[List[Dict]]: 发布信息列表或None（如果失败）
        """
        try:
            params = {
                'page': 1,
                'per_page': 20,
                'direction': 'desc'
            }
            response = requests.get(self.github_api_url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"从GitHub获取更新信息失败: {e}")
            self.logger.error(f"从GitHub获取更新信息失败: {e}")
            return None
    
    def get_all_releases(self) -> tuple:
        """
        同时获取Gitee和GitHub上的发布信息
        
        Returns:
            tuple: (gitee_releases, github_releases)
        """
        gitee_releases = self.get_gitee_releases()
        github_releases = self.get_github_releases()
        return gitee_releases, github_releases
    
    def get_best_update_source(self) -> Optional[Dict]:
        """
        获取最佳更新源（比较Gitee和GitHub上的最新版本）
        
        Returns:
            Optional[Dict]: 包含最佳更新源信息的字典，包含source、release等键
        """
        gitee_releases, github_releases = self.get_all_releases()
        
        # 获取Gitee最新稳定版本
        gitee_latest = None
        if gitee_releases:
            gitee_latest = self._find_latest_release(gitee_releases)
        
        # 获取GitHub最新稳定版本
        github_latest = None
        if github_releases:
            github_latest = self._find_latest_release(github_releases)
        
        # 比较两个平台的版本，选择最新的
        best_source = None
        
        if gitee_latest and 'tag_name' in gitee_latest:
            gitee_version = gitee_latest['tag_name']
            if self.is_newer_version(gitee_version):
                best_source = {
                    'source': 'gitee',
                    'release': gitee_latest
                }
        
        if github_latest and 'tag_name' in github_latest:
            github_version = github_latest['tag_name']
            if self.is_newer_version(github_version):
                # 如果GitHub版本比当前版本新，再与已选的最佳源比较
                if best_source is None or self._compare_versions(github_version, best_source['release']['tag_name']) > 0:
                    best_source = {
                        'source': 'github',
                        'release': github_latest
                    }
        
        return best_source
    
    def _find_latest_release(self, releases: List[Dict]) -> Optional[Dict]:
        """
        从发布信息中找出最新的稳定版本
        
        Args:
            releases: 发布信息列表
            
        Returns:
            Optional[Dict]: 最新稳定版本信息或None
        """
        if not releases:
            return None
        
        # 过滤掉预发布版本，只保留稳定版本
        stable_releases = [release for release in releases if not release.get('prerelease', False)]
        
        if not stable_releases:
            return None
        
        # 返回最新版本（假设API已经按时间倒序排列）
        return stable_releases[0]
    
    def is_newer_version(self, latest_version: str) -> bool:
        """
        检查最新版本是否比当前版本更新
        
        Args:
            latest_version: 最新版本号
            
        Returns:
            bool: 如果最新版本更新则返回True，否则返回False
        """
        return self._compare_versions(latest_version, THIS_VERSION) > 0
    
    def display_release_info(self, release: Dict, source: str) -> None:
        """
        显示发布信息
        
        Args:
            release: 发布信息字典
            source: 更新源 ('gitee' 或 'github')
        """
        source_name = "Gitee" if source == "gitee" else "GitHub"
        print(f"来自 {source_name} 的更新:")
        self.logger.info(f"来自 {source_name} 的更新:")
        
        # 根据不同平台的数据结构显示信息
        if 'tag_name' in release:
            print(f"最新版本: {release['tag_name']}")
            self.logger.info(f"最新版本: {release['tag_name']}")
            
        if 'name' in release:
            print(f"版本名称: {release['name']}")
            self.logger.info(f"版本名称: {release['name']}")
            
        if 'body' in release and release['body']:
            print(f"更新内容:\n{release['body']}")
            self.logger.info(f"更新内容:\n{release['body']}")
            
        if 'created_at' in release:
            print(f"发布时间: {release['created_at']}")
            self.logger.info(f"发布时间: {release['created_at']}")
            
        # 显示下载链接
        if 'assets' in release and release['assets']:
            print("\n下载链接:")
            self.logger.info("下载链接:")
            for asset in release['assets']:
                if 'browser_download_url' in asset:
                    print(f"- {asset.get('name', 'Unknown')}: {asset['browser_download_url']}")
                    self.logger.info(f"- {asset.get('name', 'Unknown')}: {asset['browser_download_url']}")

    def find_download_url(self, release: Dict, tag_name: str) -> Optional[str]:
        """
        在发布资产中查找匹配的下载链接
        
        Args:
            release: 发布信息字典
            tag_name: 版本标签名
            
        Returns:
            Optional[str]: 下载链接，如果未找到则返回None
        """
        if 'assets' in release and release['assets']:
            expected_filename = f"classroom_lottery_{tag_name}.zip"
            for asset in release['assets']:
                if 'browser_download_url' in asset and 'name' in asset:
                    if asset['name'] == expected_filename:
                        return asset['browser_download_url']
                    
                    # 如果没有精确匹配，尝试模糊匹配
                    if 'classroom_lottery' in asset['name'] and '.zip' in asset['name']:
                        return asset['browser_download_url']
        return None

    def convert_to_mirror_url(self, url: str) -> str:
        """
        将原始GitHub下载链接转换为镜像站链接
        
        Args:
            url: 原始GitHub下载链接
            
        Returns:
            str: 镜像站下载链接
        """
        if "github.com" in url:
            # 替换为镜像站URL
            mirror_url = url.replace("https://github.com", self.github_mirror_base)
            return mirror_url
        return url

    def download_with_progress(self, url: str, filename: str) -> bool:
        """
        带进度条的文件下载功能，支持镜像站下载
        
        Args:
            url: 下载链接
            filename: 保存的文件名
            
        Returns:
            bool: 下载成功返回True，否则返回False
        """
        # 确保文件保存在正确的工作目录中
        filepath = os.path.join(self.work_dir, filename)
        
        # 如果启用了mirror_only并且是GitHub链接，则直接使用镜像站
        if self.mirror_only and "github.com" in url:
            print("使用镜像站下载...")
            self.logger.info("使用镜像站下载...")
            url = self.convert_to_mirror_url(url)
            return self._perform_download(url, filepath, filename)
        
        # 首先尝试直接下载
        print(f"开始下载: {filename}")
        self.logger.info(f"开始下载: {filename}")
        success = self._perform_download(url, filepath, filename)
        
        # 如果直接下载失败且是GitHub链接，则尝试使用镜像站下载
        if not success and "github.com" in url:
            print("尝试使用镜像站下载...")
            self.logger.info("尝试使用镜像站下载...")
            mirror_url = self.convert_to_mirror_url(url)
            success = self._perform_download(mirror_url, filepath, filename)
            
        return success
    
    def _perform_download(self, url: str, filepath: str, filename: str) -> bool:
        """
        执行实际的文件下载操作
        
        Args:
            url: 下载链接
            filepath: 保存的文件路径
            filename: 文件名
            
        Returns:
            bool: 下载成功返回True，否则返回False
        """
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            
            with open(filepath, 'wb') as file, tqdm(
                desc=filename,
                total=total_size,
                unit='B',
                unit_scale=True,
                unit_divisor=1024,
            ) as progress_bar:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        size = file.write(chunk)
                        progress_bar.update(size)
            
            print("\n下载完成!")
            self.logger.info("下载完成!")
            return True
        except Exception as e:
            print(f"\n下载失败: {e}")
            self.logger.error(f"下载失败: {e}")
            return False
    
    def extract_and_install(self, zip_filename: str) -> bool:
        """
        解压并安装更新
        
        Args:
            zip_filename: ZIP文件名
            
        Returns:
            bool: 安装成功返回True，否则返回False
        """
        try:
            zip_filepath = os.path.join(self.work_dir, zip_filename)
            
            # 检查ZIP文件是否存在
            if not os.path.exists(zip_filepath):
                print(f"找不到文件: {zip_filepath}")
                self.logger.error(f"找不到文件: {zip_filepath}")
                return False
                
            print(f"开始解压: {zip_filename}")
            self.logger.info(f"开始解压: {zip_filename}")
            
            # 解压到临时目录
            temp_dir = os.path.join(self.work_dir, "temp_extract")
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            os.makedirs(temp_dir)
            
            # 解压文件
            with zipfile.ZipFile(zip_filepath, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            print("解压完成，开始安装...")
            self.logger.info("解压完成，开始安装...")
            
            # 遍历解压后的文件并复制到工作目录
            for root, dirs, files in os.walk(temp_dir):
                # 计算相对于临时目录的相对路径
                rel_path = os.path.relpath(root, temp_dir)
                dest_path = os.path.join(self.work_dir, rel_path) if rel_path != "." else self.work_dir
                
                # 创建目标目录
                if not os.path.exists(dest_path):
                    os.makedirs(dest_path)
                
                # 复制文件
                for file in files:
                    src_file = os.path.join(root, file)
                    dest_file = os.path.join(dest_path, file)
                    
                    # 如果是调试模式且是exe文件，则复制py文件而不是exe文件
                    if self.debug_mode and file.endswith('.exe'):
                        py_file = file.replace('.exe', '.py')
                        py_src_file = os.path.join(os.path.dirname(src_file), py_file)
                        if os.path.exists(py_src_file):
                            shutil.copy2(py_src_file, dest_file.replace('.exe', '.py'))
                            self.logger.info(f"复制 {py_src_file} 到 {dest_file.replace('.exe', '.py')}")
                        else:
                            shutil.copy2(src_file, dest_file)
                            self.logger.info(f"复制 {src_file} 到 {dest_file}")
                    else:
                        shutil.copy2(src_file, dest_file)
                        self.logger.info(f"复制 {src_file} 到 {dest_file}")
            
            # 清理临时目录
            shutil.rmtree(temp_dir)
            
            print("安装完成!")
            self.logger.info("安装完成!")
            return True
        except Exception as e:
            print(f"安装失败: {e}")
            self.logger.error(f"安装失败: {e}")
            return False
    
    def wait_for_process_exit(self, process_name: str, check_interval: int = 1) -> bool:
        """
        等待指定进程退出
        
        Args:
            process_name: 进程名
            check_interval: 检查间隔（秒）
            
        Returns:
            bool: 进程退出返回True，超时返回False
        """
        try:
            import psutil
            print(f"等待进程 {process_name} 退出...")
            self.logger.info(f"等待进程 {process_name} 退出...")
            
            # 检查进程是否还存在
            while True:
                process_exists = False
                for proc in psutil.process_iter(['pid', 'name']):
                    if proc.info['name'] == process_name:
                        process_exists = True
                        break
                
                if not process_exists:
                    print(f"进程 {process_name} 已退出")
                    self.logger.info(f"进程 {process_name} 已退出")
                    return True
                    
                time.sleep(check_interval)
        except ImportError:
            print("未安装psutil库，无法检测进程状态")
            self.logger.warning("未安装psutil库，无法检测进程状态")
            # 如果没有psutil，则简单等待一段时间
            time.sleep(5)
            return True
        except Exception as e:
            print(f"检测进程状态时出错: {e}")
            self.logger.error(f"检测进程状态时出错: {e}")
            return False

def main():
    """
    主函数
    """
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="课堂抽号程序更新工具")
    parser.add_argument('-y', '--auto-download', action='store_true', help="自动下载，无需确认")
    parser.add_argument('--unzip-only', action='store_true', help="仅解压目录下已有的合法zip文件")
    parser.add_argument('--debug', action='store_true', help="调试模式，工作目录为./debug")
    parser.add_argument('--mirror-only', action='store_true', help="优先使用镜像站下载GitHub资源")
    
    args = parser.parse_args()
    
    # 初始化更新检查器
    checker = UpdateChecker(debug_mode=args.debug, mirror_only=args.mirror_only)
    
    # 如果是仅解压模式
    if args.unzip_only:
        # 查找目录下的合法zip文件
        zip_files = []
        work_dir = "./debug" if args.debug else "."
        for file in os.listdir(work_dir):
            if file.startswith("classroom_lottery_") and file.endswith(".zip"):
                zip_files.append(file)
        
        if not zip_files:
            print("未找到合法的zip文件")
            checker.logger.error("未找到合法的zip文件")
            return
            
        if len(zip_files) > 1:
            print("找到多个合法的zip文件:")
            for i, file in enumerate(zip_files):
                print(f"{i+1}. {file}")
            try:
                choice = int(input("请选择要解压的文件编号: ")) - 1
                if 0 <= choice < len(zip_files):
                    selected_file = zip_files[choice]
                else:
                    print("无效的选择")
                    return
            except ValueError:
                print("无效的输入")
                return
        else:
            selected_file = zip_files[0]
        
        print(f"开始解压安装: {selected_file}")
        checker.logger.info(f"开始解压安装: {selected_file}")
        checker.extract_and_install(selected_file)
        return
    
    # 正常更新检查流程
    print("正在检查更新...")
    checker.logger.info("正在检查更新...")
    
    best_source = checker.get_best_update_source()
    
    if best_source:
        print("\n发现新版本!")
        checker.logger.info("发现新版本!")
        checker.display_release_info(best_source['release'], best_source['source'])
        
        # 根据参数决定是否自动下载
        should_download = args.auto_download
        if not should_download:
            choice = input("\n是否要下载最新版本? (y/n): ").lower().strip()
            should_download = choice == 'y' or choice == 'yes'
            
        if should_download:
            tag_name = best_source['release']['tag_name']
            download_url = checker.find_download_url(best_source['release'], tag_name)
            
            if download_url:
                filename = f"classroom_lottery_{tag_name}.zip"
                success = checker.download_with_progress(download_url, filename)
                if success:
                    print(f"文件已保存为: {filename}")
                    checker.logger.info(f"文件已保存为: {filename}")
                    
                    # 询问是否安装
                    install_choice = input("\n是否要安装更新? (y/n): ").lower().strip()
                    if install_choice == 'y' or install_choice == 'yes':
                        # 复制update.exe为update_old.exe
                        if not args.debug:
                            if os.path.exists("update.exe"):
                                shutil.copy2("update.exe", "update_old.exe")
                                print("已复制 update.exe 为 update_old.exe")
                                checker.logger.info("已复制 update.exe 为 update_old.exe")
                                
                                # 启动update_old.exe执行解压安装
                                import subprocess
                                subprocess.Popen(["update_old.exe", "--unzip-only"])
                                print("已启动更新安装程序，即将退出...")
                                checker.logger.info("已启动更新安装程序，即将退出...")
                                sys.exit(0)
                            else:
                                # 直接解压安装
                                checker.extract_and_install(filename)
                        else:
                            # 调试模式下直接解压安装
                            checker.extract_and_install(filename)
                else:
                    print("下载失败")
                    checker.logger.error("下载失败")
            else:
                print("未找到合适的下载链接")
                checker.logger.error("未找到合适的下载链接")
    else:
        print(f"\n当前已是最新版本 ({THIS_VERSION})")
        checker.logger.info(f"当前已是最新版本 ({THIS_VERSION})")

if __name__ == "__main__":
    main()