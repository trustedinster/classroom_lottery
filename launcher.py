import sys
import os
from configparser import ConfigParser
from subprocess import Popen
from glob import glob
import json

from PySide2.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QRadioButton, QCheckBox,
                               QComboBox, QFileDialog, QMessageBox, QGroupBox, QButtonGroup)
from PySide2.QtCore import Qt


class LauncherApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("课堂抽号程序启动器")
        self.setGeometry(100, 100, 500, 600)
        self.setFixedSize(500, 600)

        # 读取配置
        self.config = ConfigParser()
        self.config_file = 'config.ini'
        self.load_config()

        # 初始化exe文件列表为空
        self.exe_files = {}
        self.selected_version = None
        self.version_group = None  # 为了兼容性，添加此变量

        # 创建界面
        self.init_ui()

    def load_config(self):
        """加载配置文件"""
        try:
            self.config.read(self.config_file, encoding='utf-8')
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法读取配置文件: {e}")



    def check_student_list(self):
        """检查是否存在学生名单"""
        try:
            if os.path.exists('students.json'):
                with open('students.json', 'r', encoding='utf-8') as f:
                    students = json.load(f)
                # 更新显示
                self.student_info_label.setText(f"已成功加载{len(students)}名学生的信息")
                return True
        except Exception as e:
            pass
        self.student_info_label.setText("未加载学生名单")
        return False

    def init_ui(self):
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 创建主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # 标题
        title_label = QLabel("课堂抽号程序启动器")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 16pt; font-weight: bold; font-family: 微软雅黑;")
        main_layout.addWidget(title_label)

        # 配置编辑区域
        config_group = QGroupBox("配置设置")
        config_layout = QVBoxLayout(config_group)

        # min_number
        min_layout = QHBoxLayout()
        min_layout.addWidget(QLabel("最小号码:"), 1)
        self.min_edit = QLineEdit()
        self.min_edit.setText(self.config.get('lottery', 'min_number', fallback='1'))
        self.min_edit.setFixedWidth(100)
        min_layout.addWidget(self.min_edit)
        config_layout.addLayout(min_layout)

        # max_number
        max_layout = QHBoxLayout()
        max_layout.addWidget(QLabel("最大号码:"), 1)
        self.max_edit = QLineEdit()
        self.max_edit.setText(self.config.get('lottery', 'max_number', fallback='48'))
        self.max_edit.setFixedWidth(100)
        max_layout.addWidget(self.max_edit)
        config_layout.addLayout(max_layout)

        # delay
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("延迟(秒):"), 1)
        self.delay_edit = QLineEdit()
        self.delay_edit.setText(self.config.get('lottery', 'delay', fallback='1'))
        self.delay_edit.setFixedWidth(100)
        delay_layout.addWidget(self.delay_edit)
        config_layout.addLayout(delay_layout)

        # keep
        keep_layout = QHBoxLayout()
        keep_layout.addWidget(QLabel("保持时间(秒):"), 1)
        self.keep_edit = QLineEdit()
        self.keep_edit.setText(self.config.get('lottery', 'keep', fallback='3'))
        self.keep_edit.setFixedWidth(100)
        keep_layout.addWidget(self.keep_edit)
        config_layout.addLayout(keep_layout)

        # 学生讲题模式
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("抽取模式:"), 1)
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("0 - 全随机模式", "0")
        self.mode_combo.addItem("1 - 学生讲题模式(正序)", "1")
        self.mode_combo.addItem("2 - 学生讲题模式(倒序)", "2")
        current_mode = self.config.get('lottery', 'student_mode', fallback='0')
        index = self.mode_combo.findData(current_mode)
        if index >= 0:
            self.mode_combo.setCurrentIndex(index)
        self.mode_combo.setFixedWidth(200)
        mode_layout.addWidget(self.mode_combo)
        config_layout.addLayout(mode_layout)

        # 语音叫号设置
        voice_layout = QHBoxLayout()
        self.voice_checkbox = QCheckBox("启用语音:")
        enable_voice = self.config.get('lottery', 'enable_voice', fallback='1')
        self.voice_checkbox.setChecked(enable_voice == '1')
        voice_layout.addWidget(self.voice_checkbox)

        voice_layout.addWidget(QLabel("叫号模板:"))
        self.voice_template_edit = QLineEdit()
        self.voice_template_edit.setText(self.config.get('lottery', 'voice_template', fallback='请{}同学回答问题'))
        voice_layout.addWidget(self.voice_template_edit)
        config_layout.addLayout(voice_layout)

        # 灵活地叫号设置
        self.dynamic_voice_layout = QCheckBox("启用灵活的形容词")
        enable_voice = self.config.get('lottery', 'dynamic_voice_layout', fallback='1')
        self.dynamic_voice_layout.setChecked(enable_voice == '1')
        voice_layout.addWidget(self.dynamic_voice_layout)

        # 语音设置区域
        voice_setting_layout = QHBoxLayout()
        voice_setting_layout.addWidget(QLabel("语速:"), 1)
        self.voice_rate_edit = QLineEdit()
        self.voice_rate_edit.setText(self.config.get('lottery', 'voice_rate', fallback='150'))
        self.voice_rate_edit.setFixedWidth(100)
        voice_setting_layout.addWidget(self.voice_rate_edit)
        config_layout.addLayout(voice_setting_layout)

        voice_volume_layout = QHBoxLayout()
        voice_volume_layout.addWidget(QLabel("音量:"), 1)
        self.voice_volume_edit = QLineEdit()
        self.voice_volume_edit.setText(self.config.get('lottery', 'voice_volume', fallback='1.0'))
        self.voice_volume_edit.setFixedWidth(100)
        voice_volume_layout.addWidget(self.voice_volume_edit)
        config_layout.addLayout(voice_volume_layout)

        # 语音选择
        voice_select_layout = QHBoxLayout()
        voice_select_layout.addWidget(QLabel("语音:"), 1)
        self.voice_combo = QComboBox()
        self.voice_combo.setFixedWidth(200)
        self.populate_voice_list()
        current_voice_id = self.config.get('lottery', 'voice_id', fallback='')
        index = self.voice_combo.findData(current_voice_id)
        if index >= 0:
            self.voice_combo.setCurrentIndex(index)
        voice_select_layout.addWidget(self.voice_combo)
        config_layout.addLayout(voice_select_layout)

        main_layout.addWidget(config_group)

        # 学生名单导入区域
        student_group = QGroupBox("学生名单管理")
        student_layout = QVBoxLayout(student_group)

        import_button = QPushButton("导入学生名单(CSV/XLSX)")
        import_button.clicked.connect(self.import_student_list)
        student_layout.addWidget(import_button)

        # 添加学生信息显示标签
        self.student_info_label = QLabel("未加载学生名单")
        self.check_student_list()
        student_layout.addWidget(self.student_info_label)

        note_label = QLabel("注意: CSV文件应包含'学号','姓名'列，Excel文件第一列为学号，第二列为姓名")
        note_label.setWordWrap(True)
        student_layout.addWidget(note_label)

        main_layout.addWidget(student_group)



        # 按钮区域
        button_layout = QHBoxLayout()

        save_button = QPushButton("保存配置")
        save_button.clicked.connect(self.save_config)
        save_button.setFixedWidth(100)
        button_layout.addWidget(save_button)

        run_button = QPushButton("运行程序")
        run_button.clicked.connect(self.run_program)
        run_button.setFixedWidth(100)
        button_layout.addWidget(run_button)

        exit_button = QPushButton("退出")
        exit_button.clicked.connect(self.close)
        exit_button.setFixedWidth(100)
        button_layout.addWidget(exit_button)

        main_layout.addLayout(button_layout)

    def save_config(self):
        """保存配置到文件"""
        try:
            # 更新配置对象
            if not self.config.has_section('lottery'):
                self.config.add_section('lottery')

            self.config.set('lottery', 'min_number', self.min_edit.text())
            self.config.set('lottery', 'max_number', self.max_edit.text())
            self.config.set('lottery', 'delay', self.delay_edit.text())
            self.config.set('lottery', 'keep', self.keep_edit.text())

            # 保存学生讲题模式配置
            mode_value = self.mode_combo.currentData()
            self.config.set('lottery', 'student_mode', mode_value)

            # 保存语音叫号配置
            self.config.set('lottery', 'enable_voice', '1' if self.voice_checkbox.isChecked() else '0')
            self.config.set('lottery', 'voice_template', self.voice_template_edit.text())
            self.config.set('lottery', 'voice_rate', self.voice_rate_edit.text())
            self.config.set('lottery', 'voice_volume', self.voice_volume_edit.text())
            self.config.set('lottery', 'voice_id', self.voice_combo.currentData() or '')
            self.config.set('lottery', 'dynamic_voice', '1'
            if self.dynamic_voice_layout.isChecked() else '0')
            # 写入文件
            with open(self.config_file, 'w', encoding='utf-8') as configfile:
                self.config.write(configfile)

            QMessageBox.information(self, "成功", "配置已保存")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存配置失败: {e}")

    def is_lottery_running(self):
        """检查是否有抽号程序或守护进程正在运行"""
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    proc_name = proc.info['name'].lower()
                    cmdline = proc.info.get('cmdline', [])
                    if ("课堂抽号程序" in proc_name or
                            "daemon.exe" in proc_name or
                            (proc_name == "python.exe" and any(
                                "daemon.py" in arg for arg in cmdline
                            ))):
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
        except ImportError:
            # 如果没有安装psutil，则跳过检查
            pass
        return False

    def close_lottery_processes(self):
        """关闭所有正在运行的抽号程序和守护进程"""
        closed = False
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    proc_name = proc.info['name'].lower()
                    cmdline = proc.info.get('cmdline', [])
                    # 关闭主程序和守护进程
                    if ("课堂抽号程序" in proc_name or
                            "daemon.exe" in proc_name or
                            (proc_name == "python.exe" and any(
                                "daemon.py" in arg for arg in cmdline
                            ))):
                        proc.terminate()
                        closed = True
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
            # 等待进程结束
            if closed:
                import time
                time.sleep(1)
        except ImportError:
            # 如果没有安装psutil，则跳过关闭过程
            pass
        return closed

    def import_student_list(self):
        """导入学生名单文件(CSV或XLSX)"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择学生名单文件",
            "",
            "Excel files (*.xlsx);;CSV files (*.csv);;All files (*.*)"
        )

        if not file_path:
            return

        student_dict = {}
        
        try:
            if file_path.endswith('.csv'):
                # 读取CSV文件
                with open(file_path, 'r', encoding='utf-8') as f:
                    import csv
                    csv_reader = csv.reader(f)
                    header = next(csv_reader, None)  # 跳过标题行
                    for row in csv_reader:
                        if len(row) >= 2:
                            try:
                                number = int(row[0])
                                name = row[1].strip()
                                if name:
                                    student_dict[number] = name
                            except (ValueError, IndexError):
                                continue
            else:  # Excel文件
                import openpyxl
                wb = openpyxl.load_workbook(file_path)
                ws = wb.active
                for row in ws.iter_rows(min_row=2, values_only=True):  # 跳过标题行
                    if len(row) >= 2:
                        try:
                            number = int(row[0])
                            name = str(row[1]).strip() if row[1] is not None else ""
                            if name:
                                student_dict[number] = name
                        except (ValueError, TypeError):
                            continue
        
            if not student_dict:
                QMessageBox.critical(self, "错误", "未能从文件中提取有效的学生信息")
                return
        
            # 保存到JSON文件
            with open('students.json', 'w', encoding='utf-8') as f:
                json.dump(student_dict, f, ensure_ascii=False, indent=2)
        
            QMessageBox.information(self, "成功", f"成功导入{len(student_dict)}名学生信息")
            # 更新显示
            self.student_info_label.setText(f"已成功加载{len(student_dict)}名学生的信息")
        
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导入失败: {str(e)}")

    def populate_voice_list(self):
        """填充语音列表"""
        try:
            import pyttsx3
            engine = pyttsx3.init()
            voices = engine.getProperty('voices')
            
            self.voice_combo.clear()
            
            if not voices:
                self.voice_combo.addItem('无可用语音', '')
            else:
                for i, voice in enumerate(voices):
                    # 显示语音名称，存储语音ID
                    display_name = f"{voice.name}" if voice.name else f"Voice {i}"
                    self.voice_combo.addItem(display_name, voice.id)
                    
        except ImportError:
            self.voice_combo.addItem('pyttsx3未安装', '')
        except Exception as e:
            self.voice_combo.addItem('获取语音列表失败', '')
            print(f"获取语音列表时出错: {e}")

    def find_daemon_exe(self):
        """查找守护进程可执行文件"""
        daemon_path = os.path.join('.', 'daemon.exe')
        if os.path.exists(daemon_path):
            return daemon_path
        # 如果没有exe文件，尝试使用Python脚本
        daemon_py = os.path.join('.', 'daemon.py')
        if os.path.exists(daemon_py):
            return ['python', daemon_py]
        return None

    def run_program(self):
        """运行选中的程序版本"""
        # 先保存配置
        self.save_config()

        # 查找守护进程
        daemon_exe = self.find_daemon_exe()
        if not daemon_exe:
            QMessageBox.critical(self, "错误", "未找到守护进程(daemon.exe或daemon.py)")
            return

        # 检查是否已经有抽号程序在运行
        if self.is_lottery_running():
            result = QMessageBox.question(
                self,
                "提示",
                "已经有一个抽号程序在运行，需要关闭它才能继续。点击确定关闭运行中的程序。",
                QMessageBox.Ok | QMessageBox.Cancel
            )
            if result == QMessageBox.Ok:
                self.close_lottery_processes()
            else:
                return

        try:
            exe_path = '课堂抽号程序.exe'
            # 获取模式值
            mode_value = self.mode_combo.currentData()
            # 构建传递给主程序的参数
            program_args = [
                f"--min-number={self.min_edit.text()}",
                f"--max-number={self.max_edit.text()}",
                f"--delay={self.delay_edit.text()}",
                f"--keep={self.keep_edit.text()}",
                f"--student-mode={mode_value}",
                f"--enable-voice={'1' if self.voice_checkbox.isChecked() else '0'}",
                f"--voice-template={self.voice_template_edit.text()}",
                f"--voice-rate={self.voice_rate_edit.text()}",
                f"--voice-volume={self.voice_volume_edit.text()}",
                f"--voice-id={self.voice_combo.currentData() or ''}"
            ]
            # 构建守护进程命令
            # 统一使用 "--" 分隔符区分参数，无论使用exe还是py形式的守护进程
            if isinstance(daemon_exe, list):
                cmd = daemon_exe + [exe_path, "--"] + program_args
            else:
                cmd = [daemon_exe, exe_path, "--"] + program_args
            # 启动守护进程
            Popen(cmd, shell=True)
            QMessageBox.information(self, "提示", f"正在启动 {exe_path} (守护进程)")
            # 启动成功后自动关闭启动器
            self.close()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"启动程序失败: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    launcher = LauncherApp()
    launcher.show()
    sys.exit(app.exec_())