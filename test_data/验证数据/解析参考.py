import pandas as pd
import numpy as np

def compare_excel_files(file1, file2, primary_key, output_file="差异报告.xlsx"):
    """
    按数据项逐行比较两个Excel/CSV文件
    :param file1: 基准文件路径
    :param file2: 待比较文件路径
    :param primary_key: 主键列名（用于对齐行）
    :param output_file: 差异报告输出路径
    """
    # 读取文件（自动识别Excel/CSV）
    df1 = pd.read_excel(file1) if file1.endswith(('.xlsx', '.xls')) else pd.read_csv(file1)
    df2 = pd.read_excel(file2) if file2.endswith(('.xlsx', '.xls')) else pd.read_csv(file2)
    
    # 统一列名大小写（可选）
    df1.columns = df1.columns.str.strip()
    df2.columns = df2.columns.str.strip()
    
    # 检查主键是否存在
    if primary_key not in df1.columns or primary_key not in df2.columns:
        raise ValueError(f"主键列 '{primary_key}' 在两个文件中必须都存在")
    
    # 设置主键并对齐
    df1 = df1.set_index(primary_key)
    df2 = df2.set_index(primary_key)
    
    # 找出所有唯一主键
    all_keys = df1.index.union(df2.index)
    
    # 初始化差异报告
    diff_report = []
    
    for key in all_keys:
        # 检查行是否存在
        in_file1 = key in df1.index
        in_file2 = key in df2.index
        
        if not in_file1:
            diff_report.append({
                primary_key: key,
                "差异类型": "仅在待比较文件存在",
                "数据项": "全部",
                "基准值": "无",
                "待比较值": "存在该行"
            })
            continue
            
        if not in_file2:
            diff_report.append({
                primary_key: key,
                "差异类型": "仅在基准文件存在",
                "数据项": "全部",
                "基准值": "存在该行",
                "待比较值": "无"
            })
            continue
        
        # 逐数据项比较
        row1 = df1.loc[key]
        row2 = df2.loc[key]
        
        for column in df1.columns.intersection(df2.columns):
            val1 = row1[column]
            val2 = row2[column]
            
            # 处理NaN值
            if pd.isna(val1) and pd.isna(val2):
                continue
            if pd.isna(val1) or pd.isna(val2) or val1 != val2:
                diff_report.append({
                    primary_key: key,
                    "差异类型": "数据项不一致",
                    "数据项": column,
                    "基准值": str(val1),
                    "待比较值": str(val2)
                })
    
    # 生成差异报告
    diff_df = pd.DataFrame(diff_report)
    
    # 保存报告
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        diff_df.to_excel(writer, sheet_name="差异详情", index=False)
        
        # 添加统计信息
        stats = pd.DataFrame({
            "统计项": ["总行数(基准)", "总行数(待比较)", "仅基准存在行数", "仅待比较存在行数", "数据项不一致数"],
            "数量": [len(df1), len(df2), len(all_keys)-len(df2), len(all_keys)-len(df1), len(diff_df)]
        })
        stats.to_excel(writer, sheet_name="统计汇总", index=False)
    
    print(f"比较完成！共发现 {len(diff_df)} 个数据项差异")
    return diff_df

# 使用示例
if __name__ == "__main__":
    compare_excel_files(
        file1="基准数据.xlsx",
        file2="待比较数据.xlsx",
        primary_key="员工ID",  # 替换为你的主键列名
        output_file="数据差异报告.xlsx"
    )
