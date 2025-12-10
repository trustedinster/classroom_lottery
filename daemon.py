import os
import sys
import time
import logging
import subprocess
import argparse
from datetime import datetime
from psutil import process_iter, NoSuchProcess, AccessDenied, ZombieProcess


def setup_logging():
    """设置日志记录"""
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    log_file = os.path.join(log_dir, f'daemon_{datetime.now().strftime("%Y%m%d")}.log')
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)


def start_program(program, args):
    """启动主程序"""
    cmd = [program] + args
    logger.info(f"Starting program: {' '.join(cmd)}")
    return subprocess.Popen(cmd)


def main():
    global logger
    logger = setup_logging()
    parser = argparse.ArgumentParser(description="课堂抽号程序守护进程")
    parser.add_argument('program', help="主程序路径")
    parser.add_argument('args', nargs='*', help="传递给主程序的参数")
    parser.add_argument('--max-restarts', type=int, default=10, help="最大重启次数")
    parser.add_argument('--restart-delay', type=int, default=5, help="重启延迟(秒)")
    args = parser.parse_args()
    restart_count = 0
    process = None
    try:
        while restart_count < args.max_restarts:
            try:
                process = start_program(args.program, args.args)
                exit_code = process.wait()
                if exit_code == 0:
                    logger.info("程序正常退出，守护进程结束")
                    break
                else:
                    restart_count += 1
                    logger.warning(
                        f"程序异常退出 (代码: {exit_code}), "
                        f"重启次数: {restart_count}/{args.max_restarts}"
                    )
                    if restart_count < args.max_restarts:
                        time.sleep(args.restart_delay)
            except Exception as e:
                restart_count += 1
                logger.error(f"启动程序失败: {str(e)}")
                if restart_count < args.max_restarts:
                    time.sleep(args.restart_delay)
    except KeyboardInterrupt:
        logger.info("收到中断信号，守护进程退出")
    finally:
        if process and process.poll() is None:
            logger.info("终止主程序进程")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("强制终止主程序进程")
                process.kill()


if __name__ == '__main__':
    main()