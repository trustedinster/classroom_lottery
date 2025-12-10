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
    
    # 修复PyInstaller打包后argparse报错的问题
    # 当stderr为None时，创建一个虚拟的stderr对象
    if not sys.stderr:
        class DummyWriter:
            def write(self, data):
                logger.error(f"stderr output: {data}")
            def flush(self):
                pass
        sys.stderr = DummyWriter()
    
    parser = argparse.ArgumentParser(description="课堂抽号程序守护进程")
    parser.add_argument('program', help="主程序路径")
    parser.add_argument('args', nargs='*', help="传递给主程序的参数")
    parser.add_argument('--max-restarts', type=int, default=10, help="最大重启次数")
    parser.add_argument('--restart-delay', type=int, default=5, help="重启延迟(秒)")
    
    # 分离传递给守护进程本身的参数和传递给主程序的参数
    # 找到 '--' 分隔符
    separator_index = None
    try:
        separator_index = sys.argv.index('--')
    except ValueError:
        # 没有找到分隔符，按照原来的逻辑处理
        args = parser.parse_args()
        program_args = args.args
    else:
        # 找到了分隔符，分别解析两部分参数
        daemon_args = sys.argv[1:separator_index]
        program_args_list = sys.argv[separator_index+1:]
        
        args = parser.parse_args(daemon_args)
        program_args = program_args_list
    
    restart_count = 0
    process = None
    try:
        while restart_count < args.max_restarts:
            try:
                process = start_program(args.program, program_args)
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