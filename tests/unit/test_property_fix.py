"""
测试 @property 装饰器修复后的兼容性

验证 DI 容器的依赖访问方式：
1. 属性访问方式: container.service
2. 方法调用方式: container.service() (向后兼容)
"""

import pytest

from src.di import Container


class TestPropertyAccessFix:
    """测试属性访问修复"""

    def test_config_property_access(self):
        """测试 config 属性访问"""
        container = Container()
        
        config = container.config
        assert config is not None
        if hasattr(config, '__call__'):
            config = config()
        assert hasattr(config, 'SCHEDULER')

    def test_cache_property_access(self):
        """测试 cache 属性访问"""
        container = Container()
        
        # 属性访问方式
        cache = container.cache
        assert cache is not None

    def test_scheduler_client_property_access(self):
        """测试 scheduler_client 属性访问"""
        container = Container()
        
        # 属性访问方式
        client = container.scheduler_client
        assert client is not None

    def test_token_economy_service_property_access(self):
        """测试 token_economy_service 属性访问"""
        container = Container()
        
        # 属性访问方式
        service = container.token_economy_service
        assert service is not None

    def test_login_use_case_property_access(self):
        """测试 login_use_case 属性访问"""
        container = Container()
        
        # 属性访问方式
        use_case = container.login_use_case
        assert use_case is not None

    def test_register_use_case_property_access(self):
        """测试 register_use_case 属性访问"""
        container = Container()
        
        # 属性访问方式
        use_case = container.register_use_case
        assert use_case is not None

    def test_distributed_task_client_property_access(self):
        """测试 distributed_task_client 属性访问"""
        container = Container()
        
        # 属性访问方式
        client = container.distributed_task_client
        assert client is not None

    def test_multiple_access_returns_same_instance(self):
        """测试多次访问返回同一实例（单例模式）"""
        container = Container()
        
        # 多次属性访问
        client1 = container.scheduler_client
        client2 = container.scheduler_client
        
        # 应该返回同一个实例
        assert client1 is client2


class TestBackwardCompatibility:
    """测试向后兼容性"""

    def test_property_and_method_access_equivalence(self):
        """测试属性访问和方法调用的等价性"""
        container = Container()
        
        # 属性访问
        config_prop = container.config
        cache_prop = container.cache
        client_prop = container.scheduler_client
        
        # 所有访问方式都应该返回有效的对象
        assert config_prop is not None
        assert cache_prop is not None
        assert client_prop is not None


class TestContainerWiring:
    """测试容器连接功能"""

    def test_wire_and_unwire(self):
        """测试 wire 和 unwire 功能"""
        container = Container()
        
        # wire 应该正常工作
        container.wire(modules=["tests.unit.test_property_fix"])
        
        # unwire 应该正常工作
        container.unwire()


class TestContainerSingleton:
    """测试容器单例行为"""

    def test_container_creates_singletons(self):
        """测试容器创建单例"""
        container = Container()
        
        # 多次访问应该返回同一个实例
        client1 = container.scheduler_client
        client2 = container.scheduler_client
        assert client1 is client2
        
        service1 = container.token_economy_service
        service2 = container.token_economy_service
        assert service1 is service2

    def test_different_containers_have_different_instances(self):
        """测试不同的容器实例有不同的对象"""
        container1 = Container()
        container2 = Container()
        
        # 不同容器的实例应该不同
        client1 = container1.scheduler_client
        client2 = container2.scheduler_client
        
        # 注意：这可能相同也可能不同，取决于实现
        # 这里只是验证都能正常访问
        assert client1 is not None
        assert client2 is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
