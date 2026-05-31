import os
import time
import pickle
import logging
from collections import deque
from typing import Any, Deque, Optional

# 配置日志
def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    return logger

class RollingWindow:
    """滑动窗口数据管理类，用于存储和管理固定大小的数据流"""
    def __init__(self, size: int):
        self.size = size
        self.data: Deque[Any] = deque(maxlen=size)
        self.logger = setup_logger('RollingWindow')

    def add(self, item: Any) -> None:
        """添加数据项到窗口"""
        if len(self.data) >= self.size:
            self.logger.debug(f"滑动窗口已满({self.size}), 自动移除最早数据")
        self.data.append(item)

    def get(self) -> Deque[Any]:
        """获取当前窗口所有数据"""
        return self.data

    def get_df(self) -> 'pd.DataFrame':  # 延迟导入以避免依赖问题
        """将窗口数据转换为DataFrame"""
        try:
            import pandas as pd
            return pd.DataFrame(self.data)
        except ImportError:
            self.logger.error("pandas库未安装，无法转换为DataFrame")
            raise
        except Exception as e:
            self.logger.error(f"转换DataFrame失败: {str(e)}")
            raise

    def is_full(self) -> bool:
        """检查窗口是否已满"""
        return len(self.data) == self.size

    def count(self) -> int:
        """获取当前数据量"""
        return len(self.data)

    def clear(self) -> None:
        """清空窗口数据"""
        self.data.clear()

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, index: int) -> Any:
        return self.data[index]


class BufferManager:
    """缓冲区管理与持久化引擎"""
    def __init__(self,
                 buffer_size: int = 5000,
                 persist_threshold: int = 2000,
                 temp_dir: str = 'temp_buffers',
                 max_temp_files: int = 5):
        self.buffer_size = buffer_size
        self.persist_threshold = persist_threshold
        self.temp_dir = temp_dir
        self.max_temp_files = max_temp_files
        
        # 初始化数据缓冲区
        self.data_buffer: Deque[Any] = deque(maxlen=buffer_size)
        self.window = RollingWindow(size=1000)
        
        # 初始化日志
        self.logger = setup_logger('BufferManager')
        
        # 确保临时目录存在
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # 清理过期临时文件
        self._cleanup_temp_files()

    def add_data(self, data: Any) -> None:
        """添加数据到缓冲区和滑动窗口"""
        self.data_buffer.append(data)
        self.window.add(data)
        
        # 检查是否需要持久化
        if len(self.data_buffer) >= self.persist_threshold:
            self.persist_buffer()

    def persist_buffer(self) -> Optional[str]:
        """将缓冲区数据持久化到临时文件"""
        if len(self.data_buffer) > self.persist_threshold:  # 修正变量名
            try:
                import uuid
                temp_file = os.path.join(self.temp_dir, f"buffer_{uuid.uuid4().hex[:8]}.pkl")
                with open(temp_file, 'wb') as f:
                    pickle.dump(list(self.data_buffer), f)
                self.data_buffer = deque(maxlen=self.buffer_size)
                self.logger.info(f"缓冲区数据已持久化到: {temp_file}")
                self._cleanup_temp_files()
                return temp_file
            except Exception as e:
                self.logger.error(f"缓冲区持久化失败: {str(e)}")
                return None
        self.logger.debug(f"缓冲区数据量({len(self.data_buffer)})未达到持久化阈值({self.persist_threshold})")
        return None

    def _cleanup_temp_files(self) -> None:
        """清理过期的临时文件"""
        try:
            # 获取所有临时文件并按创建时间排序
            temp_files = [
                os.path.join(self.temp_dir, f) 
                for f in os.listdir(self.temp_dir) 
                if f.startswith('buffer_') and f.endswith('.pkl')
            ]
            
            # 按修改时间排序，保留最新的max_temp_files个文件
            temp_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            
            # 删除多余的文件
            for file in temp_files[self.max_temp_files:]:
                os.remove(file)
                self.logger.info(f"已清理过期临时文件: {file}")
        except Exception as e:
            self.logger.error(f"临时文件清理失败: {str(e)}")

    def load_from_temp(self, file_path: str) -> Optional[list]:
        """从临时文件加载数据"""
        if not os.path.exists(file_path):
            self.logger.error(f"临时文件不存在: {file_path}")
            return None
        
        try:
            with open(file_path, 'rb') as f:
                data = pickle.load(f)
            self.logger.info(f"已从临时文件加载数据: {file_path}, 共{len(data)}条记录")
            return data
        except Exception as e:
            self.logger.error(f"临时文件加载失败: {str(e)}")
            os.remove(file_path)  # 删除损坏的文件
            return None

    def get_recent_data(self, count: int = 1000) -> list:
        """获取最近的N条数据"""
        return list(self.data_buffer)[-count:]

    def get_window_data(self) -> Deque[Any]:
        """获取滑动窗口数据"""
        return self.window.get()

    def clear_all(self) -> None:
        """清空所有缓冲区和临时文件"""
        self.data_buffer.clear()
        self.window.clear()
        
        # 清理所有临时文件
        for f in os.listdir(self.temp_dir):
            if f.startswith('buffer_') and f.endswith('.pkl'):
                os.remove(os.path.join(self.temp_dir, f))
        
        self.logger.info("已清空所有缓冲区数据和临时文件")