from tkinter import ttk, messagebox, filedialog, Tk, StringVar, Label, Frame, Entry, Checkbutton, Button, Radiobutton
from configparser import ConfigParser
from subprocess import Popen
from os import path
from glob import glob
from psutil import NoSuchProcess, process_iter, AccessDenied, ZombieProcess
from time import sleep
from pandas import read_csv, read_excel
from json import load, dump


class LauncherApp:
    def __init__(self, root):
        self.root = root
        self.root.title("课堂抽号程序启动器")
        self.root.geometry("500x600")  # 增加窗口高度
        self.root.resizable(False, False)

        # 读取配置
        self.config = ConfigParser()
        self.config_file = 'config.ini'
        self.load_config()

        # 查找可用的程序版本
        self.exe_files = self.find_exe_files()
        self.selected_version = StringVar()

        # 创建界面
        self.create_widgets()

        # 设置默认选中的版本
        if self.exe_files:
            latest_version = self.get_latest_version()
            self.selected_version.set(latest_version)

        # 检查学生名单
        self.check_student_list()

        # 检查守护进程
        if not self.find_daemon_exe():
            messagebox.showwarning(
                "警告", 
                "未找到守护进程(daemon.exe或daemon.py)，程序稳定性将无法保证"
            )

    def load_config(self):
        """加载配置文件"""
        try:
            self.config.read(self.config_file, encoding='utf-8')
        except Exception as e:
            messagebox.showerror("错误", f"无法读取配置文件: {e}")

    def find_exe_files(self):
        """查找当前目录下所有的课堂抽号程序exe文件"""
        exe_pattern = path.join('.', '课堂抽号程序*.exe')
        exe_files = glob(exe_pattern)
        # 提取版本号信息
        versions = {}
        for exe in exe_files:
            basename = path.basename(exe)
            if basename == '课堂抽号程序.exe':
                versions[basename] = {'version': '1.0', 'path': exe}
            else:
                # 提取版本号，例如 课堂抽号程序2.0.exe -> 2.0
                version = basename.replace('课堂抽号程序', '').replace('.exe', '')
                versions[basename] = {'version': version, 'path': exe}
        return versions

    def get_latest_version(self):
        """获取最新版本"""
        if not self.exe_files:
            return ""

        # 简单排序，找出最大的版本号
        versions = [(v['version'], name) for name, v in self.exe_files.items()]
        versions.sort(key=lambda x: x[0], reverse=True)
        return versions[0][1]

    def check_student_list(self):
        """检查是否存在学生名单"""
        try:
            if path.exists('students.json'):
                with open('students.json', 'r', encoding='utf-8') as f:
                    students = load(f)
                # 更新显示
                self.student_info_label.config(text=f"已成功加载{len(students)}名学生的信息")
                return True
        except Exception as e:
            pass
        self.student_info_label.config(text="未加载学生名单")
        return False

    def create_widgets(self):
        # 标题
        title_label = Label(self.root, text="课堂抽号程序启动器", font=("微软雅黑", 16, "bold"))
        title_label.pack(pady=10)

        # 配置编辑区域
        config_frame = ttk.LabelFrame(self.root, text="配置设置")
        config_frame.pack(fill="both", expand="yes", padx=20, pady=10)

        # min_number
        min_frame = Frame(config_frame)
        min_frame.pack(fill="x", padx=10, pady=5)
        Label(min_frame, text="最小号码:", width=15, anchor="w").pack(side="left")
        self.min_var = StringVar(value=self.config.get('lottery', 'min_number', fallback='1'))
        Entry(min_frame, textvariable=self.min_var, width=20).pack(side="left")

        # max_number
        max_frame = Frame(config_frame)
        max_frame.pack(fill="x", padx=10, pady=5)
        Label(max_frame, text="最大号码:", width=15, anchor="w").pack(side="left")
        self.max_var = StringVar(value=self.config.get('lottery', 'max_number', fallback='48'))
        Entry(max_frame, textvariable=self.max_var, width=20).pack(side="left")

        # delay
        delay_frame = Frame(config_frame)
        delay_frame.pack(fill="x", padx=10, pady=5)
        Label(delay_frame, text="延迟(秒):", width=15, anchor="w").pack(side="left")
        self.delay_var = StringVar(value=self.config.get('lottery', 'delay', fallback='1'))
        Entry(delay_frame, textvariable=self.delay_var, width=20).pack(side="left")

        # keep
        keep_frame = Frame(config_frame)
        keep_frame.pack(fill="x", padx=10, pady=5)
        Label(keep_frame, text="保持时间(秒):", width=15, anchor="w").pack(side="left")
        self.keep_var = StringVar(value=self.config.get('lottery', 'keep', fallback='3'))
        Entry(keep_frame, textvariable=self.keep_var, width=20).pack(side="left")

        # 学生讲题模式
        mode_frame = Frame(config_frame)
        mode_frame.pack(fill="x", padx=10, pady=5)
        Label(mode_frame, text="抽取模式:", width=15, anchor="w").pack(side="left")
        self.mode_var = StringVar(value=self.config.get('lottery', 'student_mode', fallback='0'))
        mode_combo = ttk.Combobox(mode_frame, textvariable=self.mode_var, width=17)
        mode_combo['values'] = [('0 - 全随机模式'), ('1 - 学生讲题模式(正序)'), ('2 - 学生讲题模式(倒序)')]
        mode_combo['state'] = 'readonly'
        # 设置默认显示值
        current_mode = self.config.get('lottery', 'student_mode', fallback='0')
        mode_map = {'0': '0 - 全随机模式', '1': '1 - 学生讲题模式(正序)', '2': '2 - 学生讲题模式(倒序)'}
        mode_combo.set(mode_map.get(current_mode, '0 - 全随机模式'))
        mode_combo.pack(side="left")

        # 语音叫号设置
        voice_frame = Frame(config_frame)
        voice_frame.pack(fill="x", padx=10, pady=5)
        Label(voice_frame, text="启用语音:", width=15, anchor="w").pack(side="left")
        self.voice_var = StringVar(value=self.config.get('lottery', 'enable_voice', fallback='1'))
        Checkbutton(voice_frame, variable=self.voice_var, onvalue='1', offvalue='0').pack(side="left")

        Label(voice_frame, text="叫号模板:", width=15, anchor="w").pack(side="left")
        self.voice_template_var = StringVar(value=self.config.get('lottery', 'voice_template', fallback='请{}号同学回答问题'))
        Entry(voice_frame, textvariable=self.voice_template_var, width=20).pack(side="left")

        # 学生名单导入区域
        student_list_frame = ttk.LabelFrame(self.root, text="学生名单管理")
        student_list_frame.pack(fill="both", expand="yes", padx=20, pady=10)

        Button(student_list_frame, text="导入学生名单(CSV/XLSX)", command=self.import_student_list).pack(pady=5)
        # 添加学生信息显示标签
        self.student_info_label = Label(student_list_frame, text="未加载学生名单")
        self.student_info_label.pack(pady=5)
        Label(student_list_frame, text="注意: CSV文件应包含'学号','姓名'列，Excel文件第一列为学号，第二列为姓名",
                 wraplength=400, justify="left").pack(pady=5)

        # 版本选择区域
        version_frame = ttk.LabelFrame(self.root, text="程序版本选择")
        version_frame.pack(fill="both", expand="yes", padx=20, pady=10)

        if self.exe_files:
            for name in self.exe_files.keys():
                Radiobutton(
                    version_frame,
                    text=name,
                    variable=self.selected_version,
                    value=name
                ).pack(anchor="w", padx=10, pady=2)
        else:
            Label(version_frame, text="未找到可执行文件").pack(padx=10, pady=10)

        # 按钮区域
        button_frame = Frame(self.root)
        button_frame.pack(pady=20)

        Button(button_frame, text="保存配置", command=self.save_config, width=12).pack(side="left", padx=10)
        Button(button_frame, text="运行程序", command=self.run_program, width=12).pack(side="left", padx=10)
        Button(button_frame, text="退出", command=self.root.quit, width=12).pack(side="left", padx=10)

    def save_config(self):
        """保存配置到文件"""
        try:
            # 更新配置对象
            if not self.config.has_section('lottery'):
                self.config.add_section('lottery')

            self.config.set('lottery', 'min_number', self.min_var.get())
            self.config.set('lottery', 'max_number', self.max_var.get())
            self.config.set('lottery', 'delay', self.delay_var.get())
            self.config.set('lottery', 'keep', self.keep_var.get())

            # 保存学生讲题模式配置
            # 从组合框的值中提取模式数字
            mode_value = self.mode_var.get().split(' ')[0]
            self.config.set('lottery', 'student_mode', mode_value)

            # 保存语音叫号配置
            self.config.set('lottery', 'enable_voice', self.voice_var.get())
            self.config.set('lottery', 'voice_template', self.voice_template_var.get())

            # 写入文件
            with open(self.config_file, 'w', encoding='utf-8') as configfile:
                self.config.write(configfile)

            messagebox.showinfo("成功", "配置已保存")
        except Exception as e:
            messagebox.showerror("错误", f"保存配置失败: {e}")

    def is_lottery_running(self):
        """检查是否有抽号程序或守护进程正在运行"""
        for proc in process_iter(['pid', 'name', 'cmdline']):
            try:
                proc_name = proc.info['name'].lower()
                if ("课堂抽号程序" in proc_name or 
                    "daemon.exe" in proc_name or 
                    (proc_name == "python.exe" and any(
                        "daemon.py" in cmdline for cmdline in proc.cmdline()
                    ))):
                    return True
            except (NoSuchProcess, AccessDenied, ZombieProcess):
                pass
        return False

    def close_lottery_processes(self):
        """关闭所有正在运行的抽号程序和守护进程"""
        closed = False
        for proc in process_iter(['pid', 'name']):
            try:
                proc_name = proc.info['name'].lower()
                # 关闭主程序和守护进程
                if ("课堂抽号程序" in proc_name or 
                    "daemon.exe" in proc_name or 
                    (proc_name == "python.exe" and any(
                        "daemon.py" in cmdline for cmdline in proc.cmdline()
                    ))):
                    proc.terminate()
                    closed = True
            except (NoSuchProcess, AccessDenied, ZombieProcess):
                pass
        # 等待进程结束
        if closed:
            sleep(1)
        return closed

    def import_student_list(self):
        """导入学生名单文件(CSV或XLSX)"""
        file_path = filedialog.askopenfilename(
            title="选择学生名单文件",
            filetypes=[("Excel files", "*.xlsx"), ("CSV files", "*.csv"), ("All files", "*.*")]
        )

        if not file_path:
            return

        try:
            # 读取文件
            if file_path.endswith('.csv'):
                df = read_csv(file_path, encoding='utf-8')
            else:
                df = read_excel(file_path)

            # 检查列名
            if len(df.columns) < 2:
                messagebox.showerror("错误", "文件至少需要两列（学号和姓名）")
                return

            # 获取学号和姓名列
            student_dict = {}
            # 尝试识别列名
            if '学号' in df.columns and '姓名' in df.columns:
                number_col, name_col = '学号', '姓名'
            elif 'number' in [col.lower() for col in df.columns] and 'name' in [col.lower() for col in df.columns]:
                number_col = [col for col in df.columns if col.lower() == 'number'][0]
                name_col = [col for col in df.columns if col.lower() == 'name'][0]
            else:
                # 默认使用前两列
                number_col, name_col = df.columns[0], df.columns[1]

            # 构建字典
            for _, row in df.iterrows():
                try:
                    number = int(row[number_col])
                    name = str(row[name_col]).strip()
                    if name:  # 只有姓名非空才添加
                        student_dict[number] = name
                except (ValueError, KeyError):
                    continue

            if not student_dict:
                messagebox.showerror("错误", "未能从文件中提取有效的学生信息")
                return

            # 保存到JSON文件
            with open('students.json', 'w', encoding='utf-8') as f:
                dump(student_dict, f, ensure_ascii=False, indent=2)

            messagebox.showinfo("成功", f"成功导入{len(student_dict)}名学生信息")
            # 更新显示
            self.student_info_label.config(text=f"已成功加载{len(student_dict)}名学生的信息")

        except Exception as e:
            messagebox.showerror("错误", f"导入失败: {str(e)}")

    def find_daemon_exe(self):
        """查找守护进程可执行文件"""
        daemon_path = path.join('.', 'daemon.exe')
        if path.exists(daemon_path):
            return daemon_path
        # 如果没有exe文件，尝试使用Python脚本
        daemon_py = path.join('.', 'daemon.py')
        if path.exists(daemon_py):
            return ['python', daemon_py]
        return None

    def run_program(self):
        """运行选中的程序版本"""
        # 先保存配置
        self.save_config()

        selected = self.selected_version.get()
        if not selected:
            messagebox.showwarning("警告", "请先选择一个程序版本")
            return

        if selected not in self.exe_files:
            messagebox.showerror("错误", "选择的程序版本不存在")
            return

        # 查找守护进程
        daemon_exe = self.find_daemon_exe()
        if not daemon_exe:
            messagebox.showerror("错误", "未找到守护进程(daemon.exe或daemon.py)")
            return

        # 检查是否已经有抽号程序在运行
        if self.is_lottery_running():
            result = messagebox.askokcancel(
                "提示", 
                "已经有一个抽号程序在运行，需要关闭它才能继续。点击确定关闭运行中的程序。"
            )
            if result:
                self.close_lottery_processes()
            else:
                return

        try:
            exe_path = self.exe_files[selected]['path']
            # 从组合框的值中提取模式数字
            mode_value = self.mode_var.get().split(' ')[0]
            # 构建传递给主程序的参数
            program_args = [
                f"--min-number={self.min_var.get()}",
                f"--max-number={self.max_var.get()}",
                f"--delay={self.delay_var.get()}",
                f"--keep={self.keep_var.get()}",
                f"--student-mode={mode_value}",
                f"--enable-voice={self.voice_var.get()}",
                f"--voice-template={self.voice_template_var.get()}"
            ]
            # 构建守护进程命令
            if isinstance(daemon_exe, list):
                cmd = daemon_exe + [exe_path] + program_args
            else:
                cmd = [daemon_exe, exe_path] + program_args
            # 启动守护进程
            Popen(cmd, shell=True)
            messagebox.showinfo("提示", f"正在启动 {selected} (守护进程)")
            # 启动成功后自动关闭启动器
            self.root.quit()
        except Exception as e:
            messagebox.showerror("错误", f"启动程序失败: {e}")


if __name__ == "__main__":
    root = Tk()
    app = LauncherApp(root)
    root.mainloop()