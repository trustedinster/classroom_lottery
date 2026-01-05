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
from main import DataManager, init_logger, OptimizedClassroomSampler
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

def run_optimized_fairness_test(iterations=10000, n_students=48):
    """
    运行优化算法的公平性测试
    
    Args:
        iterations (int): 测试迭代次数，默认10000次
        n_students (int): 学生总数，默认48
        
    Returns:
        dict: 包含每个数字及其出现次数的字典
    """
    print(f"开始进行优化算法公平性测试，总共 {iterations} 次抽号...")
    
    # 创建优化的抽样器
    sampler = OptimizedClassroomSampler(n_students=n_students)
    
    # 预热抽样器，让权重分布进入稳定状态
    print("正在预热抽样器...")
    for _ in range(n_students):
        sampler.select()
    print("预热完成")
    
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
        
        # 执行一次抽号（从0到n_students-1，需要转换为1到n_students）
        selected_index = sampler.select()
        number = selected_index + 1  # 转换为1-based编号
        
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

def run_legacy_fairness_test(iterations=10000):
    """
    运行传统随机算法的公平性测试（用于对比）
    
    Args:
        iterations (int): 测试迭代次数，默认10000次
        
    Returns:
        dict: 包含每个数字及其出现次数的字典
    """
    print(f"开始进行传统随机算法公平性测试，总共 {iterations} 次抽号...")
    
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
        
        # 执行一次抽号（使用传统的随机数生成）
        number = main.get_random_number()
        
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
    # 确保所有号码都在结果中（即使出现次数为0）
    observed_freq = []
    expected_freq = []
    
    # 获取最大号码数
    total_numbers = max(results.keys()) if results else 48  # 默认48个号码
    expected_count = iterations / total_numbers  # 每个号码的期望出现次数
    
    for i in range(1, total_numbers + 1):
        observed_freq.append(results.get(i, 0))
        expected_freq.append(expected_count)
    
    # 执行卡方检验
    chi2_statistic, p_value = stats.chisquare(observed_freq, expected_freq)
    
    return chi2_statistic, p_value

def analyze_consecutive_selections(results, iterations):
    """
    分析连续选择的情况
    
    Args:
        results (list): 按顺序记录的抽号结果列表
        iterations (int): 总测试次数
        
    Returns:
        dict: 包含连续选择分析结果的字典
    """
    # 需要传入顺序列表而不是计数字典
    print("连续选择分析需要顺序数据，此函数暂时不适用于当前的计数模式")
    return {}

def display_results(results, iterations, algorithm_name="优化算法"):
    """
    显示测试结果
    
    Args:
        results (dict): 测试结果字典
        iterations (int): 总测试次数
        algorithm_name (str): 算法名称
    """
    print(f"\n==================== {algorithm_name}测试结果 ====================")
    print(f"{'号码':<6} {'出现次数':<10} {'概率':<10} {'理论概率':<12}")
    print("-" * 45)
    
    # 按号码排序显示结果
    sorted_results = sorted(results.items())
    
    for number, count in sorted_results:
        probability = count / iterations * 100
        # 理论概率基于号码总数均匀分布的情况
        theoretical_prob = 1/len(results) * 100
        print(f"{number:<6} {count:<10} {probability:<9.3f}% {theoretical_prob:<11.3f}%")
    
    # 显示统计信息
    print(f"\n==================== {algorithm_name}统计信息 ====================")
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
    expected_count = iterations / len(results)
    max_deviation = max(abs(min_count - expected_count), abs(max_count - expected_count))
    deviation_percentage = (max_deviation / expected_count) * 100
    
    print(f"最大偏差: {max_deviation:.2f} ({deviation_percentage:.2f}%)")
    
    # 执行卡方检验
    print(f"\n==================== {algorithm_name}卡方检验 ====================")
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

def save_results_to_file(results, filename="fairness_test_results.txt", algorithm_name="优化算法"):
    """
    将测试结果保存到文件
    
    Args:
        results (dict): 测试结果字典
        filename (str): 输出文件名
        algorithm_name (str): 算法名称
    """
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(f"{algorithm_name}课堂抽号程序公平性测试结果\n")
        f.write("=" * 30 + "\n")
        
        sorted_results = sorted(results.items())
        for number, count in sorted_results:
            f.write(f"{number}: {count}\n")
    
    print(f"\n详细结果已保存到文件: {filename}")

def run_comparison_test():
    """运行对比测试，比较优化算法和传统算法"""
    print("开始对比测试：优化算法 vs 传统随机算法")
    
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
    
    n_students_input = input("请输入学生总数 (默认48): ").strip()
    if n_students_input == "":
        n_students = 48
    else:
        n_students = int(n_students_input)
    
    if n_students <= 0:
        print("学生总数必须大于0，使用默认值48")
        n_students = 48
    
    print("\n" + "="*50)
    print("开始测试优化算法...")
    optimized_results = run_optimized_fairness_test(iterations, n_students)
    display_results(optimized_results, iterations, "优化算法")
    
    print("\n" + "="*50)
    print("开始测试传统算法...")
    legacy_results = run_legacy_fairness_test(iterations)
    display_results(legacy_results, iterations, "传统算法")
    
    # 保存结果
    save_results_to_file(optimized_results, "optimized_fairness_test_results.txt", "优化算法")
    save_results_to_file(legacy_results, "legacy_fairness_test_results.txt", "传统算法")
    
    return optimized_results, legacy_results

def run_main():
    """主函数"""
    print("课堂抽号程序公平性测试工具")
    print("=" * 30)
    print("1. 测试优化算法")
    print("2. 测试传统算法") 
    print("3. 对比测试")
    
    choice = input("请选择测试类型 (1/2/3，默认1): ").strip()
    
    if choice == "2":
        # 运行传统算法测试
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
        
        results = run_legacy_fairness_test(iterations)
        display_results(results, iterations, "传统算法")
        save_results_to_file(results, "legacy_fairness_test_results.txt", "传统算法")
        return results
        
    elif choice == "3":
        # 运行对比测试
        return run_comparison_test()
        
    else:  # 默认选择1
        # 运行优化算法测试
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
        
        n_students_input = input("请输入学生总数 (默认48): ").strip()
        if n_students_input == "":
            n_students = 48
        else:
            n_students = int(n_students_input)
        
        if n_students <= 0:
            print("学生总数必须大于0，使用默认值48")
            n_students = 48
        
        results = run_optimized_fairness_test(iterations, n_students)
        display_results(results, iterations, "优化算法")
        save_results_to_file(results, "optimized_fairness_test_results.txt", "优化算法")
        return results

if __name__ == "__main__":
    # 运行测试并返回结果字典
    test_results = run_main()