# 测试数据集约定

## 概述
本文件记录了CNAP生理数据与IMU传感器数据测试集的对应关系，确保测试过程中数据同步的准确性。

## 数据对应关系
| CNAP数据集 | IMU数据集 | 说明 |
|------------|-----------|------|
| D:\UI重构\test\cnapdata\1.txt | D:\UI重构\test\imudata\log0.txt | 基础测试用例，包含正常驾驶场景下的生理和传感器数据 |
| D:\UI重构\test\cnapdata\2.txt | D:\UI重构\test\imudata\log1.txt | 包含急加速、急刹车场景的数据 |
| D:\UI重构\test\cnapdata\3.txt | D:\UI重构\test\imudata\log2.txt | 包含转弯和变道场景的数据 |
| D:\UI重构\test\cnapdata\4.txt | D:\UI重构\test\imudata\log3.txt | 包含复杂交通场景的数据 |
| D:\UI重构\test\cnapdata\5.txt | D:\UI重构\test\imudata\log4.txt | 包含异常驾驶行为的数据 |

## 使用方法
1. 在测试CNAP数据源时，请确保使用对应的IMU数据源
2. 测试脚本中已配置为使用1.txt和log0.txt作为默认测试数据
3. 如需测试其他数据集组合，请修改test_data_source.py中的文件路径配置

## 时间戳同步
- CNAP数据和IMU数据已通过时间戳同步器进行对齐
- 同步策略采用线性插值方法，确保时间序列数据的一致性

## 注意事项
- 所有测试数据均为模拟数据，仅用于功能测试
- 实际应用中请使用真实采集的数据