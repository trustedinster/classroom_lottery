# -*- coding: utf-8 -*-
"""
课堂号数抽取程序（PySide2重构版）- 解决线程安全问题
"""
import sys
import json
import pickle
import os
import logging
from datetime import datetime
from random import choice, randint
from threading import Thread, Lock
from tempfile import NamedTemporaryFile
from shutil import move

from winsound import SND_ASYNC, SND_FILENAME, PlaySound
import keyboard
from PySide2.QtWidgets import (QApplication, QDialog, QLabel, QVBoxLayout,
                               QSystemTrayIcon, QMenu, QAction, QMessageBox)
from PySide2.QtCore import Qt, QTimer, Signal, QObject
from PySide2.QtGui import QIcon, QFont, QPalette, QColor, QPixmap, QImage
from PIL import Image, ImageDraw
from configparser import ConfigParser
from argparse import ArgumentParser
import pyttsx3

# ==================== 全局配置 ====================
ICON_FILE = 'assets/icon.ico'
SOUND_FILE = 'assets/rise_enable.wav'

# 配置文件读取
config = ConfigParser()
config.read('config.ini', encoding='utf-8')
MIN_NUMBER = config.getint('lottery', 'min_number', fallback=1)
MAX_NUMBER = config.getint('lottery', 'max_number', fallback=48)
DELAY = config.getint('lottery', 'delay', fallback=3)
KEEP = config.getint('lottery', 'keep', fallback=3)
STUDENT_MODE = config.getint('lottery', 'student_mode', fallback=0)
ENABLE_VOICE = config.getint('lottery', 'enable_voice', fallback=1)
VOICE_TEMPLATE = config.get('lottery', 'voice_template', fallback='请{}号同学回答问题')

# 学生名单
STUDENTS = {}
try:
    if os.path.exists('students.json'):
        with open('students.json', 'r', encoding='utf-8') as f:
            STUDENTS = json.load(f)
        STUDENTS = {int(k): v for k, v in STUDENTS.items()}
except Exception as e:
    pass

WINDOW_WIDTH = 300
WINDOW_HEIGHT = 150
TRANSPARENCY = 0.8
HOTKEY = 'alt'
DATA_FILE = 'lottery_data.pkl'
LOG_DIR = 'logs'
MODE_FLAG_FILE = '3sec_show.conf.start'

# 全局状态
SHOW_MODE_3SEC = os.path.exists(MODE_FLAG_FILE)
logger = logging.getLogger(__name__)
data_manager = None
hotkey_listener = None
tray_icon = None
app = None

# 学生讲题模式相关
student_mode_used_numbers = set()
student_mode_current_min = MIN_NUMBER
student_mode_current_max = MAX_NUMBER


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
            logging.StreamHandler()
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
    sound_path = os.path.join(os.getcwd(), SOUND_FILE)
    if os.path.exists(sound_path):
        try:
            Thread(
                target=lambda: PlaySound(sound_path, SND_FILENAME | SND_ASYNC),
                daemon=True
            ).start()
            logger.info(f'启动音效播放成功：{SOUND_FILE}')
        except Exception as e:
            logger.warning(f'启动音效播放失败：{str(e)}')
    else:
        logger.warning(f'未找到启动音效文件：{SOUND_FILE}')


# ==================== 数据管理 ====================
class DataManager:
    def __init__(self):
        self.degraded = False
        self.data = self._init_data()
        self.lock = Lock()
        if not os.path.exists(os.path.join(os.getcwd(), "temp")):
            os.makedirs(os.path.join(os.getcwd(), "temp"))

    def _init_data(self):
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

            if 'numbers' not in data:
                data['numbers'] = default_data['numbers']
            else:
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
            temp_dir = os.path.join(os.getcwd(), "temp")
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)

            with NamedTemporaryFile(
                    dir=temp_dir, prefix='temp_', suffix='.pkl',
                    delete=False, mode='wb'
            ) as temp_file:
                temp_path = temp_file.name
                pickle.dump(data, temp_file)

            target_path = os.path.join(os.getcwd(), DATA_FILE)
            if os.path.exists(target_path):
                os.remove(target_path)
            move(temp_path, target_path)
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
            try:
                with self.lock:
                    self.data['numbers'][number] += 1
                    write_thread = Thread(target=self._write_data, args=(self.data.copy(),))
                    write_thread.daemon = True
                    write_thread.start()
                    write_thread.join(timeout=2.0)
                    if write_thread.is_alive():
                        logger.warning('数据写入超时，可能存在数据丢失')
            except Exception as e:
                logger.error(f'更新统计数据时发生错误: {str(e)}')

        thread = Thread(target=_do_update)
        thread.daemon = True
        thread.start()


# ==================== 号数抽取逻辑 ====================
def get_random_number():
    global data_manager, student_mode_used_numbers

    if STUDENT_MODE == 1:
        return get_student_mode_number_forward()
    elif STUDENT_MODE == 2:
        return get_student_mode_number_reverse()

    selected_number = randint(MIN_NUMBER, MAX_NUMBER)
    logger.info(f'全随机模式抽中号数：{selected_number}（降级模式：{data_manager.degraded}）')
    return selected_number


def get_student_mode_number_forward():
    global student_mode_used_numbers, student_mode_current_min

    logger.debug(
        f'正序模式开始 - 当前min值: {student_mode_current_min}, 已使用号码: {sorted(student_mode_used_numbers)}')

    if student_mode_current_min + 10 > MAX_NUMBER:
        logger.debug(f'正序模式 - min+10 > MAX_NUMBER，进入下一轮')
        student_mode_current_min = MIN_NUMBER

    range_start = student_mode_current_min
    range_end = min(student_mode_current_min + 10, MAX_NUMBER)

    logger.debug(f'正序模式 - 区间: [{range_start}, {range_end}]')

    valid_numbers = [n for n in range(range_start, range_end + 1)
                     if n not in student_mode_used_numbers]

    logger.debug(f'正序模式 - 区间内有效号码: {valid_numbers}')

    while not valid_numbers and range_end < MAX_NUMBER:
        logger.debug(f'正序模式 - 当前区间无有效号码，寻找新区间')
        student_mode_current_min = range_end + 1
        range_start = student_mode_current_min
        range_end = min(student_mode_current_min + 10, MAX_NUMBER)
        valid_numbers = [n for n in range(range_start, range_end + 1)
                         if n not in student_mode_used_numbers]
        logger.debug(f'正序模式 - 新区间: [{range_start}, {range_end}], 有效号码: {valid_numbers}')

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

    selected_number = choice(valid_numbers)
    student_mode_used_numbers.add(selected_number)

    old_min = student_mode_current_min
    student_mode_current_min = selected_number
    logger.info(
        f'学生讲题模式(正序)抽中号数：{selected_number}，区间：[{range_start}, {range_end}], min值从{old_min}更新为{student_mode_current_min}')

    logger.debug(f'当前已使用号码: {sorted(student_mode_used_numbers)}')
    return selected_number


def get_student_mode_number_reverse():
    global student_mode_used_numbers, student_mode_current_max

    logger.debug(
        f'倒序模式开始 - 当前max值: {student_mode_current_max}, 已使用号码: {sorted(student_mode_used_numbers)}')

    if student_mode_current_max - 10 < MIN_NUMBER:
        logger.debug(f'倒序模式 - max-10 < MIN_NUMBER，进入下一轮')
        student_mode_current_max = MAX_NUMBER

    range_start = max(student_mode_current_max - 10, MIN_NUMBER)
    range_end = student_mode_current_max

    logger.debug(f'倒序模式 - 区间: [{range_start}, {range_end}]')

    valid_numbers = [n for n in range(range_start, range_end + 1)
                     if n not in student_mode_used_numbers]

    logger.debug(f'倒序模式 - 区间内有效号码: {valid_numbers}')

    while not valid_numbers and range_start > MIN_NUMBER:
        logger.debug(f'倒序模式 - 当前区间无有效号码，寻找新区间')
        student_mode_current_max = range_start - 1
        range_start = max(student_mode_current_max - 10, MIN_NUMBER)
        range_end = student_mode_current_max
        valid_numbers = [n for n in range(range_start, range_end + 1)
                         if n not in student_mode_used_numbers]
        logger.debug(f'倒序模式 - 新区间: [{range_start}, {range_end}], 有效号码: {valid_numbers}')

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

    selected_number = choice(valid_numbers)
    student_mode_used_numbers.add(selected_number)

    old_max = student_mode_current_max
    student_mode_current_max = selected_number
    logger.info(
        f'学生讲题模式(倒序)抽中号数：{selected_number}，区间：[{range_start}, {range_end}], max值从{old_max}更新为{student_mode_current_max}')

    logger.debug(f'当前已使用号码: {sorted(student_mode_used_numbers)}')
    return selected_number


# ==================== 抽号窗口 ====================
class LotteryWindow(QDialog):
    def __init__(self, number, parent=None):
        super().__init__(parent)
        self.number = number
        self.scroll_count = 0
        self.max_scroll_times = DELAY
        self.display_text = STUDENTS.get(self.number, str(self.number))

        self.initUI()

        if SHOW_MODE_3SEC:
            self.start_scroll()
        else:
            self.show_result()

    def initUI(self):
        self.setWindowTitle('课堂抽号')
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowOpacity(TRANSPARENCY)

        # 设置窗口位置（右上角）
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - WINDOW_WIDTH - 20, 0)

        # 创建布局
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)

        # 号码标签
        self.number_label = QLabel()
        self.number_label.setAlignment(Qt.AlignCenter)
        self.number_label.setFont(QFont('黑体', 40 if STUDENTS else 60, QFont.Bold))
        self.number_label.setStyleSheet("color: #333333; background-color: white; border-radius: 10px;")
        self.number_label.setFixedHeight(60 if STUDENTS else 90)
        layout.addWidget(self.number_label)

        # 姓名标签
        if STUDENTS:
            self.name_label = QLabel()
            self.name_label.setAlignment(Qt.AlignCenter)
            self.name_label.setFont(QFont('黑体', 20, QFont.Bold))
            self.name_label.setStyleSheet("color: #333333; background-color: white; border-radius: 10px;")
            self.name_label.setFixedHeight(40)
            layout.addWidget(self.name_label)
        else:
            self.name_label = None

        self.setLayout(layout)

    def start_scroll(self):
        self.scroll_count += 1
        random_num = randint(MIN_NUMBER, MAX_NUMBER)
        random_display_text = STUDENTS.get(random_num, str(random_num))

        if self.name_label:
            self.number_label.setText(f"№{random_num}")
            self.name_label.setText(random_display_text if random_display_text != str(random_num) else "")
        else:
            self.number_label.setText(random_display_text)

        if self.scroll_count < self.max_scroll_times:
            interval = 50 + (self.scroll_count * 10)
            QTimer.singleShot(min(interval, 500), self.start_scroll)
        else:
            self.stop_scroll()

    def stop_scroll(self):
        if self.name_label:
            self.number_label.setText(f"№{self.number}")
            self.number_label.setStyleSheet("color: red; background-color: white; border-radius: 10px;")
            self.name_label.setText(self.display_text if self.display_text != str(self.number) else "")
            self.name_label.setStyleSheet("color: red; background-color: white; border-radius: 10px;")
        else:
            self.number_label.setText(self.display_text)
            self.number_label.setStyleSheet("color: red; background-color: white; border-radius: 10px;")

        logger.info('三秒变动模式：已定格最终结果')
        QTimer.singleShot(KEEP * 1000, self.close)

    def show_result(self):
        if self.name_label:
            self.number_label.setText(f"№{self.number}")
            self.number_label.setStyleSheet("color: red; background-color: white; border-radius: 10px;")
            self.name_label.setText(self.display_text if self.display_text != str(self.number) else "")
            self.name_label.setStyleSheet("color: red; background-color: white; border-radius: 10px;")
        else:
            self.number_label.setText(self.display_text)
            self.number_label.setStyleSheet("color: red; background-color: white; border-radius: 10px;")

        logger.info('直接显示模式：已显示结果')
        QTimer.singleShot(KEEP * 1000, self.close)

    def keyPressEvent(self, event):
        # ESC键不再关闭窗口
        pass


# ==================== 通信对象 ====================
class Communicator(QObject):
    show_window_signal = Signal(int)

    def __init__(self):
        super().__init__()


# ==================== 语音叫号功能 ====================
def speak_number(number):
    if not ENABLE_VOICE:
        return

    try:
        student_name = STUDENTS.get(number)
        if student_name:
            speak_text = VOICE_TEMPLATE.format(student_name)
        else:
            speak_text = VOICE_TEMPLATE.format(str(number) + '号')

        engine = pyttsx3.init()
        engine.setProperty('rate', 200)
        engine.setProperty('volume', 1.0)
        engine.say(speak_text)
        engine.runAndWait()
        logger.info(f'语音叫号成功: {speak_text}')
    except Exception as e:
        logger.error(f'语音叫号功能异常: {str(e)}')


# ==================== 主应用 ====================
class LotteryApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        self.current_window = None  # 添加窗口引用

        # 初始化通信对象
        self.communicator = Communicator()
        self.communicator.show_window_signal.connect(self.show_lottery_window)

        # 创建托盘
        self.create_tray_icon()

        # 启动快捷键监听
        self.start_hotkey_listener()

        # 播放启动音效
        play_startup_sound()

    def create_tray_icon(self):
        global tray_icon
        icon_path = os.path.join(os.getcwd(), ICON_FILE)

        try:
            icon = QIcon(icon_path)
            logger.info(f'成功加载图标文件：{ICON_FILE}')
        except Exception as e:
            logger.warning(f'图标文件加载失败，使用默认图标：{str(e)}')
            # 创建默认图标
            pixmap = Image.new('RGB', (64, 64), 'red')
            draw = ImageDraw.Draw(pixmap)
            draw.ellipse((10, 10, 54, 54), fill='darkred')
            # 转换为QIcon
            qim = QImage(pixmap)
            icon = QIcon(QPixmap.fromImage(qim))

        tray_icon = QSystemTrayIcon(icon, self.app)
        tray_icon.setToolTip('课堂抽号（快捷键：按alt）')

        # 创建托盘菜单
        tray_menu = QMenu()
        exit_action = QAction("退出程序", self.app)
        exit_action.triggered.connect(self.exit_app)
        tray_menu.addAction(exit_action)

        tray_icon.setContextMenu(tray_menu)
        tray_icon.show()
        logger.info('托盘功能启动成功')

    def start_hotkey_listener(self):
        global hotkey_listener
        try:
            keyboard.add_hotkey(HOTKEY, self.on_hotkey)
            hotkey_listener = Thread(target=keyboard.wait)
            hotkey_listener.daemon = True
            hotkey_listener.start()
            logger.info(f'快捷键监听启动成功（{HOTKEY}）')
            return True
        except Exception as e:
            logger.error(f'快捷键注册失败：{str(e)}')
            QMessageBox.warning(None, '警告', f'快捷键注册失败，可能存在冲突！')
            return False

    def on_hotkey(self):
        try:
            number = get_random_number()
            data_manager.update_stat(number)

            # 通过信号触发主线程中的窗口显示
            self.communicator.show_window_signal.emit(number)

            # 语音播放
            if ENABLE_VOICE:
                speak_thread = Thread(target=speak_number, args=(number,))
                speak_thread.daemon = True
                speak_thread.start()
        except Exception as e:
            logger.error(f'快捷键触发失败：{str(e)}')
            QMessageBox.warning(None, '警告', '抽号失败，请重试！')

    def show_lottery_window(self, number):
        # 关闭已存在的窗口（如果有）
        if self.current_window is not None:
            self.current_window.close()
        
        # 创建并持久化窗口引用
        self.current_window = LotteryWindow(number)
        self.current_window.show()

    def exit_app(self):
        global tray_icon
        logger.info('用户通过托盘退出程序')
        try:
            if hotkey_listener:
                keyboard.unhook_all()
        except:
            pass

        if tray_icon:
            tray_icon.hide()

        self.app.quit()
        sys.exit(0)

    def run(self):
        return self.app.exec_()


# ==================== 主程序入口 ====================
def main():
    global data_manager, app
    init_logger()
    data_manager = DataManager()

    app = LotteryApp()
    sys.exit(app.run())


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        if logger:
            logger.critical(f'程序崩溃：{str(e)}', exc_info=True)
        else:
            print(f'程序崩溃：{str(e)}')
        try:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setText('程序运行出错，请查看logs目录下的日志文件！')
            msg_box.exec_()
        except:
            pass
        sys.exit(1)

# 命令行参数处理
parser = ArgumentParser()
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
