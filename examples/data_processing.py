"""
examples/data_processing.py
数据处理示例 - 展示数据分析能力
"""

def process_sales_data():
    """模拟销售数据处理"""
    import random
    import statistics
    import json
    from datetime import datetime, timedelta
    
    print("=" * 60)
    print("销售数据处理演示")
    print("=" * 60)
    
    # 生成模拟销售数据
    print("\n1. 生成模拟销售数据...")
    products = ['Laptop', 'Phone', 'Tablet', 'Monitor', 'Keyboard']
    sales_data = []
    
    start_date = datetime(2024, 1, 1)
    for i in range(1000):
        product = random.choice(products)
        quantity = random.randint(1, 10)
        price = random.uniform(100, 2000)
        date = start_date + timedelta(days=random.randint(0, 90))
        
        sales_data.append({
            'id': i + 1,
            'product': product,
            'quantity': quantity,
            'price': price,
            'revenue': quantity * price,
            'date': date.strftime('%Y-%m-%d')
        })
    
    print(f"生成 {len(sales_data)} 条销售记录")
    
    # 数据分析
    print("\n2. 数据分析...")
    
    # 按产品汇总
    product_stats = {}
    for sale in sales_data:
        product = sale['product']
        if product not in product_stats:
            product_stats[product] = {
                'count': 0,
                'total_quantity': 0,
                'total_revenue': 0,
                'prices': []
            }
        
        stats = product_stats[product]
        stats['count'] += 1
        stats['total_quantity'] += sale['quantity']
        stats['total_revenue'] += sale['revenue']
        stats['prices'].append(sale['price'])
    
    # 计算统计信息
    print("\n3. 统计结果:")
    print("-" * 40)
    
    total_revenue = sum(sale['revenue'] for sale in sales_data)
    print(f"总营收: ${total_revenue:,.2f}")
    
    for product, stats in product_stats.items():
        avg_price = statistics.mean(stats['prices'])
        revenue_share = (stats['total_revenue'] / total_revenue) * 100
        
        print(f"\n{product}:")
        print(f"  销售数量: {stats['count']}")
        print(f"  总销量: {stats['total_quantity']}")
        print(f"  营收: ${stats['total_revenue']:,.2f}")
        print(f"  平均价格: ${avg_price:.2f}")
        print(f"  营收占比: {revenue_share:.1f}%")
    
    # 找到最佳销售日
    print("\n4. 最佳销售日分析...")
    daily_sales = {}
    for sale in sales_data:
        day = sale['date']
        daily_sales[day] = daily_sales.get(day, 0) + sale['revenue']
    
    if daily_sales:
        best_day = max(daily_sales.items(), key=lambda x: x[1])
        print(f"最佳销售日: {best_day[0]}")
        print(f"当日营收: ${best_day[1]:,.2f}")
    
    # 生成报告
    print("\n5. 生成分析报告...")
    report = {
        'summary': {
            'total_records': len(sales_data),
            'total_revenue': total_revenue,
            'unique_products': len(product_stats),
            'date_range': {
                'start': min(s['date'] for s in sales_data),
                'end': max(s['date'] for s in sales_data)
            }
        },
        'product_analysis': {
            product: {
                'sales_count': stats['count'],
                'total_quantity': stats['total_quantity'],
                'total_revenue': stats['total_revenue'],
                'average_price': statistics.mean(stats['prices']),
                'revenue_share': (stats['total_revenue'] / total_revenue) * 100
            }
            for product, stats in product_stats.items()
        },
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    print(f"\n报告已生成，包含 {len(report['product_analysis'])} 个产品分析")
    
    return report

def text_analysis():
    """文本数据分析"""
    print("\n" + "=" * 60)
    print("文本数据分析演示")
    print("=" * 60)
    
    # 示例文本
    text = """
    人工智能是计算机科学的一个分支，它企图了解智能的实质，并生产出一种新的能以人类智能相似的方式做出反应的智能机器。
    该领域的研究包括机器人、语言识别、图像识别、自然语言处理和专家系统等。人工智能从诞生以来，理论和技术日益成熟，
    应用领域也不断扩大，可以设想，未来人工智能带来的科技产品，将会是人类智慧的容器。
    """
    
    print("分析文本:")
    print(f'"{text[:50]}..."')
    
    # 基本统计
    words = text.split()
    sentences = text.replace('。', '.').split('.')
    
    print(f"\n统计结果:")
    print(f"  字符数: {len(text)}")
    print(f"  单词数: {len(words)}")
    print(f"  句子数: {len([s for s in sentences if s.strip()])}")
    
    # 词频分析
    word_freq = {}
    for word in words:
        word = word.strip('.,，。!！?？')
        if word:
            word_freq[word] = word_freq.get(word, 0) + 1
    
    # 最常见的词
    common_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]
    
    print(f"\n最常见的10个词:")
    for word, freq in common_words:
        print(f"  {word}: {freq}次")
    
    return {
        'text': text,
        'stats': {
            'characters': len(text),
            'words': len(words),
            'sentences': len([s for s in sentences if s.strip()])
        },
        'common_words': dict(common_words)
    }

def run_data_processing_demo():
    """运行数据处理演示"""
    results = {}
    
    results['sales_analysis'] = process_sales_data()
    results['text_analysis'] = text_analysis()
    
    print("\n" + "=" * 60)
    print("数据处理演示完成!")
    print("=" * 60)
    
    return results

if __name__ == "__main__":
    run_data_processing_demo()
