#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试课堂抽号程序的公平性
运行大量模拟抽号操作并统计每个号码出现的频率
"""

import sys
import os
import pickle
import scipy.stats as stats

# 添加主程序目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入必要的函数和类
import main
from main import DataManager, init_logger
import threading
import time

def run_single_test(data_manager):
    """执行一次抽号测试"""
    # 设置全局data_manager变量
    main.data_manager = data_manager
    
    # 获取一个随机数
    number = main.get_random_number()

    # 更新统计数据（模拟正常流程）
    data_manager.update_stat(number)
    
    return number

def run_fairness_test(iterations=10000):
    """
    运行公平性测试
    
    Args:
        iterations (int): 测试迭代次数，默认10000次
        
    Returns:
        dict: 包含每个数字及其出现次数的字典
    """
    print(f"开始进行公平性测试，总共 {iterations} 次抽号...")
    
    # 初始化日志系统（DataManager需要logger）
    init_logger()
    
    # 创建测试用的数据管理器
    data_manager = DataManager()
    
    # 设置全局data_manager变量
    main.data_manager = data_manager
    
    # 结果统计字典
    results = {}
    
    # 记录开始时间
    start_time = time.time()
    
    # 运行指定次数的测试
    for i in range(iterations):
        # 显示进度
        if (i + 1) % (iterations // 10) == 0:
            progress = (i + 1) / iterations * 100
            print(f"进度: {progress:.1f}% ({i+1}/{iterations})")
        
        # 执行一次抽号
        number = run_single_test(data_manager)
        
        # 统计结果
        if number in results:
            results[number] += 1
        else:
            results[number] = 1
    
    # 计算耗时
    elapsed_time = time.time() - start_time
    
    print(f"\n测试完成!")
    print(f"总耗时: {elapsed_time:.2f} 秒")
    print(f"平均每次抽号耗时: {elapsed_time/iterations*1000:.4f} 毫秒")
    
    return results

def chi_square_test(results, iterations):
    """
    执行卡方检验以评估公平性
    
    Args:
        results (dict): 测试结果字典
        iterations (int): 总测试次数
        
    Returns:
        tuple: (chi2_statistic, p_value)
    """
    # 确保所有48个号码都在结果中（即使出现次数为0）
    observed_freq = []
    expected_freq = []
    
    total_numbers = 48  # 总共48个号码
    expected_count = iterations / total_numbers  # 每个号码的期望出现次数
    
    for i in range(1, total_numbers + 1):
        observed_freq.append(results.get(i, 0))
        expected_freq.append(expected_count)
    
    # 执行卡方检验
    chi2_statistic, p_value = stats.chisquare(observed_freq, expected_freq)
    
    return chi2_statistic, p_value

def display_results(results, iterations):
    """
    显示测试结果
    
    Args:
        results (dict): 测试结果字典
        iterations (int): 总测试次数
    """
    print("\n==================== 测试结果 ====================")
    print(f"{'号码':<6} {'出现次数':<10} {'概率':<10} {'理论概率':<12}")
    print("-" * 45)
    
    # 按号码排序显示结果
    sorted_results = sorted(results.items())
    
    for number, count in sorted_results:
        probability = count / iterations * 100
        # 理论概率基于48个号码均匀分布的情况
        theoretical_prob = 1/48 * 100
        print(f"{number:<6} {count:<10} {probability:<9.3f}% {theoretical_prob:<11.3f}%")
    
    # 显示统计信息
    print("\n==================== 统计信息 ====================")
    print(f"总测试次数: {iterations}")
    print(f"出现的不同号码数量: {len(results)}")
    
    # 计算最小和最大出现次数
    min_count = min(results.values())
    max_count = max(results.values())
    min_number = [num for num, count in results.items() if count == min_count][0]
    max_number = [num for num, count in results.items() if count == max_count][0]
    
    print(f"出现最少的号码: {min_number} (出现 {min_count} 次)")
    print(f"出现最多的号码: {max_number} (出现 {max_count} 次)")
    
    # 计算偏差
    expected_count = iterations / 48
    max_deviation = max(abs(min_count - expected_count), abs(max_count - expected_count))
    deviation_percentage = (max_deviation / expected_count) * 100
    
    print(f"最大偏差: {max_deviation:.2f} ({deviation_percentage:.2f}%)")
    
    # 执行卡方检验
    print("\n==================== 卡方检验 ====================")
    try:
        chi2_stat, p_value = chi_square_test(results, iterations)
        print(f"卡方统计量: {chi2_stat:.4f}")
        print(f"P值: {p_value:.4f}")
        
        # 解释结果
        alpha = 0.05  # 显著性水平
        if p_value > alpha:
            print(f"结果: P值 > {alpha}，无法拒绝原假设，分布与均匀分布无显著差异")
            print("结论: 抽号算法是公平的")
        else:
            print(f"结果: P值 <= {alpha}，拒绝原假设，分布与均匀分布存在显著差异")
            print("结论: 抽号算法可能存在不公平性")
    except Exception as e:
        print(f"卡方检验执行失败: {e}")

def save_results_to_file(results, filename="fairness_test_results.txt"):
    """
    将测试结果保存到文件
    
    Args:
        results (dict): 测试结果字典
        filename (str): 输出文件名
    """
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("课堂抽号程序公平性测试结果\n")
        f.write("=" * 30 + "\n")
        
        sorted_results = sorted(results.items())
        for number, count in sorted_results:
            f.write(f"{number}: {count}\n")
    
    print(f"\n详细结果已保存到文件: {filename}")

def run_main():
    """主函数"""
    print("课堂抽号程序公平性测试工具")
    print("=" * 30)
    
    # 获取用户输入的测试次数
    try:
        iterations = input("请输入测试次数 (默认10000): ").strip()
        if iterations == "":
            iterations = 10000
        else:
            iterations = int(iterations)
            
        if iterations <= 0:
            raise ValueError("测试次数必须大于0")
    except ValueError as e:
        print(f"输入错误: {e}")
        print("使用默认测试次数 10000")
        iterations = 10000
    
    # 运行测试
    results = run_fairness_test(iterations)
    
    # 显示结果
    display_results(results, iterations)
    
    # 保存结果到文件
    save_results_to_file(results)
    
    return results

if __name__ == "__main__":
    # 运行测试并返回结果字典
    test_results = run_main()