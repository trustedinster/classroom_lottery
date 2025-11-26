# -*- coding: utf-8 -*-
"""
课堂号数抽取程序（Windows 7/10适配）- 带启动音效版
新增：启动播放rise_enable.wav、使用icon.ico图标
新增：支持显示学生姓名而非仅学号
"""
import tkinter as tk
from tkinter import messagebox
import json
import pickle
import os
import logging
from datetime import datetime
import random
import threading
import tempfile
import shutil
import sys
import winsound  # 新增：Windows内置音频播放
import keyboard
import pystray
from PIL import Image, ImageDraw
import configparser
import argparse

# ==================== 全局配置 ====================
# 新增：资源文件路径
ICON_FILE = 'assets/icon.ico'
SOUND_FILE = 'assets/rise_enable.wav'

# 尝试从配置文件读取，如果失败则使用默认值
config = configparser.ConfigParser()
config.read('config.ini', encoding='utf-8')
MIN_NUMBER = config.getint('lottery', 'min_number', fallback=1)
MAX_NUMBER = config.getint('lottery', 'max_number', fallback=48)
DELAY = config.getint('lottery', 'delay', fallback=3)
KEEP = config.getint('lottery', 'keep', fallback=3)
# 学生讲题模式配置
STUDENT_MODE = config.getint('lottery', 'student_mode', fallback=0)  # 0=关闭, 1=正序, 2=倒序
ENABLE_VOICE = config.getint('lottery', 'enable_voice', fallback=1)
VOICE_TEMPLATE = config.get('lottery', 'voice_template', fallback='请{}号同学回答问题')

# 新增：学生名单
STUDENTS = {}
try:
    if os.path.exists('students.json'):
        with open('students.json', 'r', encoding='utf-8') as f:
            STUDENTS = json.load(f)
        # 确保键是整数
        STUDENTS = {int(k): v for k, v in STUDENTS.items()}
except Exception as e:
    pass

TEN_DIGITS = [1, 2, 3, 4]
UNIT_DIGITS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
BASE_WEIGHT = 100
UNIT_PENALTY = 20
OTHER_PENALTY = 10
WINDOW_WIDTH = 200
WINDOW_HEIGHT = 100
TRANSPARENCY = 0.8
HOTKEY = 'alt'
DATA_FILE = 'lottery_data.pkl'
LOG_DIR = 'logs'
MODE_FLAG_FILE = '3sec_show.conf.start'

# 全局状态
SHOW_MODE_3SEC = os.path.exists(MODE_FLAG_FILE)
logger = None
data_manager = None
hotkey_listener = None
tray_icon = None
root = None  # 主根窗口

# 学生讲题模式相关全局变量
student_mode_used_numbers = set()  # 已经被抽取的号码
student_mode_current_min = MIN_NUMBER  # 正序模式当前最小值
student_mode_current_max = MAX_NUMBER  # 倒序模式当前最大值


# ==================== 资源路径处理（适配打包后环境） ====================
def get_resource_path(relative_path):
    """获取资源文件路径，适配开发环境和打包后环境"""
    try:
        # 打包后路径（pyinstaller会设置此变量）
        base_path = sys._MEIPASS
    except Exception:
        # 开发环境路径
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# ==================== 日志初始化 ====================
def init_logger():
    global logger
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, f'lottery_{datetime.now().strftime("%Y%m%d")}.log')

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logger = logging.getLogger(__name__)
    mode_text = "全随机模式"
    if STUDENT_MODE == 1:
        mode_text = "学生讲题模式(正序)"
    elif STUDENT_MODE == 2:
        mode_text = "学生讲题模式(倒序)"
    logger.info(f'程序启动 - 显示模式：{"三秒变动模式" if SHOW_MODE_3SEC else "直接显示模式"} - 抽取模式：{mode_text}')
    logger.info(f'配置参数: MIN_NUMBER={MIN_NUMBER}, MAX_NUMBER={MAX_NUMBER}, STUDENT_MODE={STUDENT_MODE}')
    logger.info(f'语音叫号配置: ENABLE_VOICE={ENABLE_VOICE}, VOICE_TEMPLATE={VOICE_TEMPLATE}')
    return logger


# ==================== 启动音效播放 ====================
def play_startup_sound():
    """播放启动音效，失败不影响主程序"""
    sound_path = get_resource_path(SOUND_FILE)
    if os.path.exists(sound_path):
        try:
            # 异步播放音效，避免阻塞启动
            threading.Thread(
                target=lambda: winsound.PlaySound(sound_path, winsound.SND_FILENAME | winsound.SND_ASYNC),
                daemon=True
            ).start()
            logger.info(f'启动音效播放成功：{SOUND_FILE}')
        except Exception as e:
            logger.warning(f'启动音效播放失败：{str(e)}')
    else:
        logger.warning(f'未找到启动音效文件：{SOUND_FILE}（路径：{sound_path}）')


# ==================== 数据管理 ====================
class DataManager:
    def __init__(self):
        self.degraded = False
        self.data = self._init_data()
        self.lock = threading.Lock()
        if not os.path.exists(os.getcwd() + "\\temp"):
            os.makedirs(os.getcwd() + "\\temp")


    def _init_data(self):
        # 创建一个简单的数字计数字典，每个数字独立计数
        default_data = {
            'numbers': {i: 0 for i in range(MIN_NUMBER, MAX_NUMBER + 1)}
        }
        if not os.path.exists(DATA_FILE):
            logger.info(f'未找到历史数据文件，初始化默认数据')
            if not self._write_data(default_data):
                logger.warning('默认数据写入失败，将在首次抽号后重试')
            return default_data

        try:
            with open(DATA_FILE, 'rb') as f:
                data = pickle.load(f)
            # 确保所有数字都在数据中
            if 'numbers' not in data:
                data['numbers'] = default_data['numbers']
            else:
                # 确保所有数字都存在，缺失的数字初始化为0
                for i in range(MIN_NUMBER, MAX_NUMBER + 1):
                    if i not in data['numbers']:
                        data['numbers'][i] = 0

            logger.info('历史数据读取成功')
            return data
        except Exception as e:
            self.degraded = True
            logger.error(f'历史数据读取失败，启用降级模式：{str(e)}')
            return default_data

    def _write_data(self, data):
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                    dir=os.getcwd() + "\\temp", prefix='temp_', suffix='.pkl',
                    delete=False, mode='wb'
            ) as temp_file:
                temp_path = temp_file.name
                pickle.dump(data, temp_file)

            if os.path.exists(os.getcwd() + "\\" + DATA_FILE):
                os.remove(os.getcwd() + "\\" + DATA_FILE)
            shutil.move(temp_path, os.getcwd() + "\\" + DATA_FILE)
            logger.debug('数据原子写入成功')
            return True
        except Exception as e:
            logger.error(f'数据写入失败：{str(e)}')
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                    logger.debug(f'已清理临时文件：{temp_path}')
                except Exception as e2:
                    logger.warning(f'临时文件清理失败：{str(e2)}')
            return False

    def update_stat(self, number):
        def _do_update():
            with self.lock:
                # 直接增加对应数字的计数
                self.data['numbers'][number] += 1
                write_thread = threading.Thread(target=self._write_data, args=(self.data.copy(),))
                write_thread.daemon = True
                write_thread.start()
                write_thread.join(timeout=1.0)
                if write_thread.is_alive():
                    logger.warning('数据写入超时，可能存在数据丢失')

        thread = threading.Thread(target=_do_update)
        thread.daemon = True
        thread.start()


# ==================== 号数抽取逻辑 ====================
def get_random_number():
    global data_manager, student_mode_used_numbers
    # 根据不同模式选择号码
    
    # 学生讲题模式（正序）
    if STUDENT_MODE == 1:
        return get_student_mode_number_forward()
    
    # 学生讲题模式（倒序）
    if STUDENT_MODE == 2:
        return get_student_mode_number_reverse()
    
    # 默认全随机模式
    valid_numbers = list(range(MIN_NUMBER, MAX_NUMBER + 1))
    # 排除已经使用过的号码
    valid_numbers = [n for n in valid_numbers if n not in student_mode_used_numbers]
    
    if not valid_numbers:
        # 所有号码都已使用，重置列表
        student_mode_used_numbers.clear()
        # 重置学生讲题模式的当前值
        global student_mode_current_min, student_mode_current_max
        student_mode_current_min = MIN_NUMBER
        student_mode_current_max = MAX_NUMBER
        logger.info(f'全随机模式 - 所有号码已使用，重置列表。当前已使用号码数: {len(student_mode_used_numbers)}')
        valid_numbers = list(range(MIN_NUMBER, MAX_NUMBER + 1))
        
    selected_number = random.choice(valid_numbers)
    student_mode_used_numbers.add(selected_number)
    
    logger.info(f'全随机模式抽中号数：{selected_number}（降级模式：{data_manager.degraded}）')
    logger.debug(f'当前已使用号码: {sorted(student_mode_used_numbers)}')
    return selected_number


def get_student_mode_number_forward():
    """学生讲题模式 - 正序"""
    global student_mode_used_numbers, student_mode_current_min
    
    logger.debug(f'正序模式开始 - 当前min值: {student_mode_current_min}, 已使用号码: {sorted(student_mode_used_numbers)}')
    
    # 检查是否需要进入下一轮（min+10 > MAX_NUMBER）
    if student_mode_current_min + 10 > MAX_NUMBER:
        logger.debug(f'正序模式 - min+10 > MAX_NUMBER，进入下一轮')
        student_mode_current_min = MIN_NUMBER
    
    # 确定当前抽取区间 [current_min, current_min+10]
    range_start = student_mode_current_min
    range_end = min(student_mode_current_min + 10, MAX_NUMBER)
    
    logger.debug(f'正序模式 - 区间: [{range_start}, {range_end}]')
    
    # 获取该区间内未被使用的号码
    valid_numbers = [n for n in range(range_start, range_end + 1) 
                    if n not in student_mode_used_numbers]
    
    logger.debug(f'正序模式 - 区间内有效号码: {valid_numbers}')
    
    # 如果当前区间没有可用号码，需要寻找下一个区间
    while not valid_numbers and range_end < MAX_NUMBER:
        logger.debug(f'正序模式 - 当前区间无有效号码，寻找新区间')
        # 更新current_min为下一个区间的起点
        student_mode_current_min = range_end + 1
        range_start = student_mode_current_min
        range_end = min(student_mode_current_min + 10, MAX_NUMBER)
        valid_numbers = [n for n in range(range_start, range_end + 1) 
                        if n not in student_mode_used_numbers]
        logger.debug(f'正序模式 - 新区间: [{range_start}, {range_end}], 有效号码: {valid_numbers}')
    
    # 检查是否所有号码都已使用，如果是，则重置列表
    all_numbers = set(range(MIN_NUMBER, MAX_NUMBER + 1))
    if all_numbers.issubset(student_mode_used_numbers):
        logger.info('正序模式 - 所有号码已使用，重置列表')
        student_mode_used_numbers.clear()
        student_mode_current_min = MIN_NUMBER
        range_start = student_mode_current_min
        range_end = min(student_mode_current_min + 10, MAX_NUMBER)
        valid_numbers = [n for n in range(range_start, range_end + 1) 
                        if n not in student_mode_used_numbers]
        logger.debug(f'正序模式 - 重置后区间: [{range_start}, {range_end}], 有效号码: {valid_numbers}')
    
    # 从有效号码中随机选择一个
    selected_number = random.choice(valid_numbers)
    student_mode_used_numbers.add(selected_number)
    
    # 更新current_min为选中的号码
    old_min = student_mode_current_min
    student_mode_current_min = selected_number
    logger.info(f'学生讲题模式(正序)抽中号数：{selected_number}，区间：[{range_start}, {range_end}], min值从{old_min}更新为{student_mode_current_min}')
    
    logger.debug(f'当前已使用号码: {sorted(student_mode_used_numbers)}')
    return selected_number


def get_student_mode_number_reverse():
    """学生讲题模式 - 倒序"""
    global student_mode_used_numbers, student_mode_current_max
    
    logger.debug(f'倒序模式开始 - 当前max值: {student_mode_current_max}, 已使用号码: {sorted(student_mode_used_numbers)}')
    
    # 检查是否需要进入下一轮（max-10 < MIN_NUMBER）
    if student_mode_current_max - 10 < MIN_NUMBER:
        logger.debug(f'倒序模式 - max-10 < MIN_NUMBER，进入下一轮')
        student_mode_current_max = MAX_NUMBER
    
    # 确定当前抽取区间 [current_max-10, current_max]
    range_start = max(student_mode_current_max - 10, MIN_NUMBER)
    range_end = student_mode_current_max
    
    logger.debug(f'倒序模式 - 区间: [{range_start}, {range_end}]')
    
    # 获取该区间内未被使用的号码
    valid_numbers = [n for n in range(range_start, range_end + 1) 
                    if n not in student_mode_used_numbers]
    
    logger.debug(f'倒序模式 - 区间内有效号码: {valid_numbers}')
    
    # 如果当前区间没有可用号码，需要寻找下一个区间
    while not valid_numbers and range_start > MIN_NUMBER:
        logger.debug(f'倒序模式 - 当前区间无有效号码，寻找新区间')
        # 更新current_max为下一个区间的终点
        student_mode_current_max = range_start - 1
        range_start = max(student_mode_current_max - 10, MIN_NUMBER)
        range_end = student_mode_current_max
        valid_numbers = [n for n in range(range_start, range_end + 1) 
                        if n not in student_mode_used_numbers]
        logger.debug(f'倒序模式 - 新区间: [{range_start}, {range_end}], 有效号码: {valid_numbers}')
    
    # 检查是否所有号码都已使用，如果是，则重置列表
    all_numbers = set(range(MIN_NUMBER, MAX_NUMBER + 1))
    if all_numbers.issubset(student_mode_used_numbers):
        logger.info('倒序模式 - 所有号码已使用，重置列表')
        student_mode_used_numbers.clear()
        student_mode_current_max = MAX_NUMBER
        range_start = max(student_mode_current_max - 10, MIN_NUMBER)
        range_end = student_mode_current_max
        valid_numbers = [n for n in range(range_start, range_end + 1) 
                        if n not in student_mode_used_numbers]
        logger.debug(f'倒序模式 - 重置后区间: [{range_start}, {range_end}], 有效号码: {valid_numbers}')
    
    # 从有效号码中随机选择一个
    selected_number = random.choice(valid_numbers)
    student_mode_used_numbers.add(selected_number)
    
    # 更新current_max为选中的号码
    old_max = student_mode_current_max
    student_mode_current_max = selected_number
    logger.info(f'学生讲题模式(倒序)抽中号数：{selected_number}，区间：[{range_start}, {range_end}], max值从{old_max}更新为{student_mode_current_max}')
    
    logger.debug(f'当前已使用号码: {sorted(student_mode_used_numbers)}')
    return selected_number


class LotteryWindow(tk.Tk):
    def __init__(self, number):
        super().__init__()
        self.number = number
        self.is_scrolling = False
        self.scroll_count = 0
        self.max_scroll_times = DELAY  # 减少滚动次数以实现更平稳的停止
        
        # 新增：如果有学生姓名则使用姓名，否则使用号码
        self.display_text = STUDENTS.get(self.number, str(self.number))
        
        self._init_window()

    def _init_window(self):
        self.title('课堂抽号')
        self.geometry(f'{WINDOW_WIDTH}x{WINDOW_HEIGHT}')
        self.attributes('-topmost', True)
        self.attributes('-alpha', TRANSPARENCY)
        self.overrideredirect(True)
        
        # 绑定ESC键退出
        self.bind('<Escape>', lambda e: self.destroy())
        self.focus_set()

        # 右上角显示
        screen_width = self.winfo_screenwidth()
        x = screen_width - WINDOW_WIDTH - 20
        y = 0
        self.geometry(f'{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{x}+{y}')

        # 号数标签
        self.number_label = tk.Label(
            self, text='', font=('黑体', 40 if STUDENTS else 60, 'bold'), fg='#333333', bg='white'
        )
        self.number_label.pack(fill=tk.BOTH, expand=True)

        # 如果有学生名单，添加姓名标签
        if STUDENTS:
            self.name_label = tk.Label(
                self, text='', font=('黑体', 20, 'bold'), fg='#333333', bg='white'
            )
            self.name_label.pack(fill=tk.BOTH, expand=True)
        else:
            self.name_label = None

        # self.bind('<FocusOut>', self.on_focus_out)

        if SHOW_MODE_3SEC:
            self.start_scroll()
        else:
            self.show_result()

    def start_scroll(self):
        self.is_scrolling = True
        self.scroll_count += 1
        random_num = random.randint(MIN_NUMBER, MAX_NUMBER)
        random_display_text = STUDENTS.get(random_num, str(random_num))
        
        if self.name_label:
            # 分别显示学号和姓名
            self.number_label.config(text=f"№{random_num}")
            self.name_label.config(text=random_display_text if random_display_text != str(random_num) else "")
        else:
            self.number_label.config(text=random_display_text)
        
        # 实现逐渐减慢的滚动效果
        if self.scroll_count < self.max_scroll_times:
            # 随着滚动次数增加，间隔时间逐渐增加，实现减速效果
            interval = 50 + (self.scroll_count * 10)  # 从50ms开始，逐渐增加到350ms
            self.after(min(interval, 500), self.start_scroll)
        else:
            self.stop_scroll()

    def stop_scroll(self):
        self.is_scrolling = False
        if self.name_label:
            # 分别显示学号和姓名
            self.number_label.config(text=f"№{self.number}", fg="red")
            self.name_label.config(text=self.display_text if self.display_text != str(self.number) else "", fg="red")
        else:
            self.number_label.config(text=self.display_text, fg="red")
            
        logger.info('三秒变动模式：已定格最终结果')
        self.after(KEEP*1000, self.destroy)


    def show_result(self):
        if self.name_label:
            # 分别显示学号和姓名
            self.number_label.config(text=f"№{self.number}", fg="red")
            self.name_label.config(text=self.display_text if self.display_text != str(self.number) else "", fg="red")
        else:
            self.number_label.config(text=self.display_text, fg="red")
            
        logger.info('直接显示模式：已显示结果')
        self.after(KEEP*1000, self.destroy)


# ==================== 托盘功能（使用指定图标） ====================
def create_tray_icon():
    global tray_icon
    icon_path = get_resource_path(ICON_FILE)
    try:
        # 尝试加载指定图标
        image = Image.open(icon_path)
        logger.info(f'成功加载图标文件：{ICON_FILE}')
    except Exception as e:
        # 加载失败时使用默认图标
        logger.warning(f'图标文件加载失败，使用默认图标：{str(e)}')
        image = Image.new('RGB', (64, 64), 'red')
        draw = ImageDraw.Draw(image)
        draw.ellipse((10, 10, 54, 54), fill='darkred')

    menu = pystray.Menu(
        pystray.MenuItem('退出程序', on_tray_exit)
    )

    tray_icon = pystray.Icon(
        name='课堂抽号',
        icon=image,
        title='课堂抽号（快捷键：按alt）',
        menu=menu
    )

    tray_thread = threading.Thread(target=tray_icon.run)
    tray_thread.daemon = True
    tray_thread.start()
    logger.info('托盘功能启动成功')


def on_tray_exit(icon, item):
    global tray_icon, hotkey_listener
    logger.info('用户通过托盘退出程序')
    try:
        if hotkey_listener:
            hotkey_listener.stop()
    except:
        pass
    icon.stop()
    if root:
        root.destroy()
    sys.exit(0)


# ==================== 快捷键监听 ====================
def on_hotkey():
    try:
        number = get_random_number()
        data_manager.update_stat(number)
        # 如果启用了语音叫号，则在新线程中播放语音
        if ENABLE_VOICE:
            speak_thread = threading.Thread(target=speak_number, args=(number,))
            speak_thread.daemon = True
            speak_thread.start()
        window = LotteryWindow(number)
        window.mainloop()
    except Exception as e:
        logger.error(f'快捷键触发失败：{str(e)}')
        messagebox.showwarning('警告', '抽号失败，请重试！')


def start_hotkey_listener():
    global hotkey_listener
    try:
        # 使用keyboard库替代pynput，检测双击shift
        keyboard.add_hotkey(HOTKEY, on_hotkey)
        hotkey_listener = threading.Thread(target=keyboard.wait)
        hotkey_listener.daemon = True
        hotkey_listener.start()
        logger.info(f'快捷键监听启动成功（双击shift）')
        return True
    except Exception as e:
        logger.error(f'快捷键注册失败：{str(e)}')
        messagebox.showwarning('警告', f'快捷键注册失败，可能存在冲突！')
        return False


# ==================== 语音叫号功能 ====================
def speak_number(number):
    """使用Windows系统TTS功能进行语音叫号，兼容Windows 7及以上版本"""
    if not ENABLE_VOICE:
        return
        
    try:
        # 构造叫号文本 - 如果有学生姓名就叫姓名，否则叫学号
        student_name = STUDENTS.get(number)
        if student_name:
            speak_text = f"请{student_name}同学回答问题"
        else:
            speak_text = VOICE_TEMPLATE.format(str(number))
        
        # Windows 7兼容的语音方法
        # 使用SAPI.SpVoice COM组件实现TTS
        import win32com.client
        speaker = win32com.client.Dispatch("SAPI.SpVoice")
        speaker.Rate = 0  # 语速 -10 到 10，默认为0
        speaker.Volume = 100  # 音量 0 到 100，默认为100
        speaker.Speak(speak_text)
        logger.info(f'语音叫号成功: {speak_text}')
    except ImportError:
        # win32com不可用时的备选方案
        logger.warning('win32com模块不可用，尝试使用其他TTS方法')
        try:
            # 尝试使用powershell调用Add-Type方式
            import subprocess
            student_name = STUDENTS.get(number)
            if student_name:
                speak_text = f"请{student_name}同学回答问题"
            else:
                speak_text = VOICE_TEMPLATE.format(str(number))
                
            ps_command = f'''
            Add-Type -AssemblyName System.speech;
            $speak = New-Object System.Speech.Synthesis.SpeechSynthesizer;
            $speak.Rate = 0;
            $speak.Volume = 100;
            $speak.Speak('{speak_text}');
            '''
            subprocess.run(["powershell", "-Command", ps_command], 
                          capture_output=True, text=True, timeout=10)
            logger.info(f'通过PowerShell语音叫号成功: {speak_text}')
        except Exception as e:
            logger.error(f'PowerShell语音叫号失败: {str(e)}')
    except Exception as e:
        logger.error(f'语音叫号功能异常: {str(e)}')


# ==================== 主程序入口（新增启动音效） ====================
def main():
    global data_manager, root
    init_logger()
    data_manager = DataManager()

    # 创建主根窗口并隐藏
    root = tk.Tk()
    root.withdraw()

    # 播放启动音效
    play_startup_sound()

    # 初始化托盘（使用指定图标）
    create_tray_icon()
    start_hotkey_listener()

    root.mainloop()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        if logger:
            logger.critical(f'程序崩溃：{str(e)}', exc_info=True)
        else:
            print(f'程序崩溃：{str(e)}')
        try:
            temp_root = tk.Tk()
            temp_root.withdraw()
            messagebox.showerror('错误', '程序运行出错，请查看logs目录下的日志文件！')
            temp_root.destroy()
        except:
            pass
        sys.exit(1)

# 如果通过命令行参数启动，则使用命令行参数覆盖配置文件
parser = argparse.ArgumentParser()
parser.add_argument('--min-number', type=int, help='最小号码')
parser.add_argument('--max-number', type=int, help='最大号码')
parser.add_argument('--delay', type=int, help='延迟秒数')
parser.add_argument('--keep', type=int, help='保持时间秒数')
parser.add_argument('--student-mode', type=int, help='学生讲题模式: 0=关闭, 1=正序, 2=倒序')
parser.add_argument('--enable-voice', type=int, help='启用语音叫号: 0=关闭, 1=开启')
parser.add_argument('--voice-template', type=str, help='语音叫号模板，使用{}作为号码占位符')
args = parser.parse_args()

if args.min_number is not None:
    MIN_NUMBER = args.min_number
if args.max_number is not None:
    MAX_NUMBER = args.max_number
if args.delay is not None:
    DELAY = args.delay
if args.keep is not None:
    KEEP = args.keep
if args.student_mode is not None:
    STUDENT_MODE = args.student_mode
if args.enable_voice is not None:
    ENABLE_VOICE = args.enable_voice
else:
    ENABLE_VOICE = config.getint('lottery', 'enable_voice', fallback=1)
    
if args.voice_template is not None:
    VOICE_TEMPLATE = args.voice_template
else:
    VOICE_TEMPLATE = config.get('lottery', 'voice_template', fallback='请{}号同学回答问题')
