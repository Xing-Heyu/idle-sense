"""
examples/simulation.py
模拟示例 - 物理、经济等系统模拟
"""

def physics_simulation():
    """物理模拟 - 抛体运动"""
    print("=" * 60)
    print("物理模拟: 抛体运动")
    print("=" * 60)
    
    # 初始条件
    v0 = 50.0  # 初始速度 (m/s)
    angle = 45.0  # 角度 (度)
    g = 9.81  # 重力加速度 (m/s²)
    
    # 转换为弧度
    theta = angle * 3.1415926535 / 180.0
    
    # 计算初始速度分量
    vx0 = v0 * math.cos(theta)
    vy0 = v0 * math.sin(theta)
    
    # 模拟参数
    dt = 0.01  # 时间步长 (秒)
    time = 0.0
    x, y = 0.0, 0.0
    vx, vy = vx0, vy0
    
    trajectory = []
    
    # 模拟直到物体落地
    while y >= 0:
        # 记录当前状态
        trajectory.append({
            'time': time,
            'x': x,
            'y': y,
            'vx': vx,
            'vy': vy
        })
        
        # 更新位置
        x += vx * dt
        y += vy * dt
        
        # 更新速度 (只考虑重力)
        vy -= g * dt
        
        # 更新时间
        time += dt
    
    # 分析结果
    if trajectory:
        last_point = trajectory[-1]
        max_height = max(point['y'] for point in trajectory)
        range_distance = last_point['x']
        flight_time = last_point['time']
        
        # 理论值
        theoretical_range = (v0**2 * math.sin(2*theta)) / g
        theoretical_max_height = (v0**2 * math.sin(theta)**2) / (2*g)
        theoretical_time = (2 * v0 * math.sin(theta)) / g
        
        print(f"\n模拟参数:")
        print(f"  初始速度: {v0} m/s")
        print(f"  发射角度: {angle}°")
        
        print(f"\n模拟结果:")
        print(f"  飞行时间: {flight_time:.2f} s")
        print(f"  最大高度: {max_height:.2f} m")
        print(f"  射程: {range_distance:.2f} m")
        
        print(f"\n理论值:")
        print(f"  飞行时间: {theoretical_time:.2f} s")
        print(f"  最大高度: {theoretical_max_height:.2f} m")
        print(f"  射程: {theoretical_range:.2f} m")
        
        print(f"\n误差:")
        print(f"  时间误差: {abs(flight_time - theoretical_time):.4f} s")
        print(f"  高度误差: {abs(max_height - theoretical_max_height):.4f} m")
        print(f"  射程误差: {abs(range_distance - theoretical_range):.4f} m")
    
    return trajectory

def economic_simulation():
    """经济模拟 - 投资复利"""
    print("\n" + "=" * 60)
    print("经济模拟: 投资复利计算")
    print("=" * 60)
    
    # 投资参数
    initial_investment = 10000.0  # 初始投资
    monthly_contribution = 500.0  # 每月追加投资
    annual_return = 8.0  # 年化收益率 (%)
    years = 30  # 投资年限
    
    # 转换为月
    months = years * 12
    monthly_return = (1 + annual_return/100) ** (1/12) - 1
    
    # 模拟
    balance = initial_investment
    history = []
    
    for month in range(months):
        # 月初追加投资
        if month > 0:
            balance += monthly_contribution
        
        # 计算收益
        interest = balance * monthly_return
        balance += interest
        
        # 记录
        if month % 12 == 0:  # 每年记录一次
            year = month // 12 + 1
            history.append({
                'year': year,
                'balance': balance,
                'total_contributions': initial_investment + monthly_contribution * month,
                'total_interest': balance - (initial_investment + monthly_contribution * month)
            })
    
    # 输出结果
    if history:
        final = history[-1]
        
        print(f"\n投资参数:")
        print(f"  初始投资: ${initial_investment:,.2f}")
        print(f"  每月追加: ${monthly_contribution:,.2f}")
        print(f"  年化收益: {annual_return}%")
        print(f"  投资年限: {years}年")
        
        print(f"\n最终结果:")
        print(f"  最终余额: ${final['balance']:,.2f}")
        print(f"  总投入: ${final['total_contributions']:,.2f}")
        print(f"  总收益: ${final['total_interest']:,.2f}")
        print(f"  收益/投入比: {final['total_interest']/final['total_contributions']:.2f}")
        
        print(f"\n里程碑:")
        for milestone in [5, 10, 15, 20, 25]:
            if milestone <= years:
                record = next((h for h in history if h['year'] == milestone), None)
                if record:
                    print(f"  第{milestone}年: ${record['balance']:,.2f}")
    
    return history

def cellular_automaton():
    """细胞自动机 - 生命游戏"""
    print("\n" + "=" * 60)
    print("细胞自动机: Conway的生命游戏")
    print("=" * 60)
    
    # 网格大小
    width, height = 20, 20
    
    # 初始状态 (滑翔机模式)
    grid = [[0 for _ in range(width)] for _ in range(height)]
    
    # 设置初始活细胞 (滑翔机)
    glider = [(1, 0), (2, 1), (0, 2), (1, 2), (2, 2)]
    for x, y in glider:
        if x < width and y < height:
            grid[y][x] = 1
    
    # 模拟步数
    steps = 10
    
    def count_neighbors(x, y):
        """计算邻居数量"""
        count = 0
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    count += grid[ny][nx]
        return count
    
    def print_grid(step):
        """打印网格"""
        print(f"\n第 {step} 代:")
        for y in range(min(height, 10)):  # 只显示前10行
            row = ''
            for x in range(min(width, 20)):  # 只显示前20列
                row += '█' if grid[y][x] else '░'
            print(row)
    
    # 初始状态
    print_grid(0)
    
    # 模拟
    for step in range(1, steps + 1):
        new_grid = [[0 for _ in range(width)] for _ in range(height)]
        
        for y in range(height):
            for x in range(width):
                neighbors = count_neighbors(x, y)
                
                # 应用规则
                if grid[y][x] == 1:  # 活细胞
                    if neighbors in [2, 3]:
                        new_grid[y][x] = 1  # 存活
                    else:
                        new_grid[y][x] = 0  # 死亡
                else:  # 死细胞
                    if neighbors == 3:
                        new_grid[y][x] = 1  # 繁殖
                    else:
                        new_grid[y][x] = 0
        
        grid = new_grid
        print_grid(step)
    
    # 统计
    total_cells = width * height
    live_cells = sum(sum(row) for row in grid)
    
    print(f"\n统计:")
    print(f"  总细胞数: {total_cells}")
    print(f"  活细胞数: {live_cells}")
    print(f"  活细胞比例: {live_cells/total_cells*100:.1f}%")
    
    return {
        'width': width,
        'height': height,
        'steps': steps,
        'final_live_cells': live_cells,
        'initial_pattern': 'glider'
    }

def run_simulation_demo():
    """运行模拟演示"""
    import math
    
    results = {}
    
    results['physics'] = physics_simulation()
    results['economics'] = economic_simulation()
    results['cellular_automaton'] = cellular_automaton()
    
    print("\n" + "=" * 60)
    print("模拟演示完成!")
    print("=" * 60)
    
    return results

if __name__ == "__main__":
    run_simulation_demo()
