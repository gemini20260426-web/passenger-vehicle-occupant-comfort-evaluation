"""
统一清除管理 — 协议接口 + 注册中心模式

行业实践参考：
  - Android LifecycleObserver：组件通过接口注册到生命周期管理器
  - Java Closeable：统一资源释放接口
  - Qt QObject 树：父对象销毁时自动级联销毁子对象
  - ServiceLocator：中心化组件注册与查找

设计原则：
  1. 所有可清除的模块实现 ClearableResource 协议
  2. 模块初始化时自动注册到 ClearableRegistry
  3. 切换数据集 / Pipeline 变更时，一键调用 registry.clear_all()
  4. 新增模块只需实现协议 + 注册，无需修改 _on_clear_all_ui

注意：ClearableResource 不使用 ABC/ABCMeta，避免与 PySide6 QWidget 的元类冲突。
"""

from typing import Dict
import logging

logger = logging.getLogger("ClearableRegistry")


class ClearableResource:
    """可清除资源协议 — 所有模块/面板/组件实现此接口

    不使用 ABC 抽象基类，只使用普通类 + NotImplementedError，
    避免 ABCMeta 与 PySide6 QWidget 的元类冲突。
    子类必须实现 clear_all() 方法。
    """

    def clear_all(self) -> None:
        """清除所有内部数据，恢复到初始空状态
        子类实现时必须清除：
          - 所有数据缓冲区（列表、字典、deque 等）
          - 所有表格/列表视图（QTableWidget, QListWidget 等）
          - 所有图表/画布（图表数据、曲线数据）
          - 所有内部状态标志（如 _is_playing, _evaluation_mode 等）
          - 所有子组件（递归调用子组件的 clear_all）
        """
        raise NotImplementedError(f"{type(self).__name__} 必须实现 clear_all()")


class ClearableRegistry:
    """统一清除注册中心（单例）

    用法：
      # 模块初始化时注册
      registry = ClearableRegistry.instance()
      registry.register("IMU可视化", self)

      # 切换数据集时一键清除
      registry.clear_all()
    """

    _instance = None

    def __init__(self):
        self._resources: Dict[str, ClearableResource] = {}
        self._order: list = []  # 保持注册顺序

    @classmethod
    def instance(cls) -> 'ClearableRegistry':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """重置单例（主要用于测试）"""
        cls._instance = None

    def register(self, name: str, resource: ClearableResource):
        """注册一个可清除资源"""
        if name in self._resources:
            logger.warning(f"覆盖已注册的资源: {name}")
        self._resources[name] = resource
        if name not in self._order:
            self._order.append(name)
        logger.debug(f"注册清除资源: {name}")

    def unregister(self, name: str):
        """注销一个可清除资源"""
        self._resources.pop(name, None)
        if name in self._order:
            self._order.remove(name)
        logger.debug(f"注销清除资源: {name}")

    def clear_all(self):
        """按注册顺序清除所有资源"""
        cleared = 0
        failed = 0
        for name in self._order:
            resource = self._resources.get(name)
            if resource is None:
                continue
            try:
                resource.clear_all()
                cleared += 1
                logger.debug(f"已清除: {name}")
            except Exception as e:
                failed += 1
                logger.error(f"清除失败 [{name}]: {e}", exc_info=True)
        logger.info(f"统一清除完成: 成功 {cleared}, 失败 {failed}, 共 {len(self._order)} 个资源")
        return cleared, failed

    @property
    def resource_count(self) -> int:
        return len(self._resources)

    @property
    def resource_names(self) -> list:
        return list(self._order)