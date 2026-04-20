"""
测试 wbi.py - B站 WBI 签名模块
"""
import time
from unittest.mock import MagicMock, patch

import pytest

from app.modules.wbi import WBISigner, sign_params


class TestWBISignerMixinKey:
    """测试 _get_mixin_key 方法"""

    def test_mixin_key_generation(self):
        """测试：混合密钥生成（B站实际 key 长度为 32）"""
        signer = WBISigner()
        # B站 img_key 和 sub_key 各 32 字符
        result = signer._get_mixin_key("a" * 32, "b" * 32)
        assert len(result) == 32
        assert isinstance(result, str)

    def test_mixin_key_deterministic(self):
        """测试：相同输入产生相同输出"""
        signer = WBISigner()
        result1 = signer._get_mixin_key("abc123" * 5 + "ab", "xyz789" * 5 + "xy")
        result2 = signer._get_mixin_key("abc123" * 5 + "ab", "xyz789" * 5 + "xy")
        assert result1 == result2

    def test_mixin_key_different_inputs(self):
        """测试：不同输入产生不同输出"""
        signer = WBISigner()
        result1 = signer._get_mixin_key("a" * 32, "b" * 32)
        result2 = signer._get_mixin_key("c" * 32, "d" * 32)
        assert result1 != result2


class TestWBISignerGetKeys:
    """测试 _get_keys 方法"""

    def test_get_keys_success(self):
        """测试：成功获取密钥"""
        signer = WBISigner()

        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "code": 0,
                "data": {
                    "wbi_img": {
                        "img_url": "https://example.com/aaaakey.jpg",
                        "sub_url": "https://example.com/bbbbsubkey.jpg"
                    }
                }
            }
            mock_get.return_value = mock_response

            img_key, sub_key = signer._get_keys()
            assert img_key == "aaaakey"
            assert sub_key == "bbbbsubkey"

    def test_get_keys_api_error(self):
        """测试：API 返回错误码"""
        signer = WBISigner()

        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {"code": -101, "message": "error"}
            mock_get.return_value = mock_response

            img_key, sub_key = signer._get_keys()
            assert img_key is None
            assert sub_key is None

    def test_get_keys_network_error(self):
        """测试：网络请求异常"""
        signer = WBISigner()

        with patch('requests.get') as mock_get:
            mock_get.side_effect = Exception("network error")

            img_key, sub_key = signer._get_keys()
            assert img_key is None
            assert sub_key is None


class TestWBISignerRefreshMixinKey:
    """测试 _refresh_mixin_key 方法"""

    def test_refresh_uses_cache(self):
        """测试：缓存有效时直接返回"""
        signer = WBISigner()
        signer._mixin_key = "cached_key_1234567890123456789012"
        signer._last_refresh = int(time.time())

        result = signer._refresh_mixin_key()
        assert result == "cached_key_1234567890123456789012"

    def test_refresh_refreshes_when_expired(self):
        """测试：缓存过期时重新获取"""
        signer = WBISigner()
        signer._mixin_key = None  # 强制刷新
        signer._last_refresh = 0

        with patch.object(signer, '_get_keys', return_value=("a" * 32, "b" * 32)):
            signer._refresh_mixin_key()
            assert signer._img_key == "a" * 32
            assert signer._sub_key == "b" * 32

    def test_refresh_raises_when_keys_fail(self):
        """测试：密钥获取失败时抛出异常"""
        signer = WBISigner()
        signer._mixin_key = None
        signer._last_refresh = 0

        with patch.object(signer, '_get_keys', return_value=(None, None)):
            with pytest.raises(ValueError) as exc_info:
                signer._refresh_mixin_key()
            assert "WBI 密钥获取失败" in str(exc_info.value)


class TestWBISignerSign:
    """测试 sign 方法"""

    def test_sign_adds_wts_and_wrid(self):
        """测试：签名添加 wts 和 w_rid"""
        signer = WBISigner()
        signer._mixin_key = "a" * 32
        signer._last_refresh = int(time.time()) + 1000

        params = {"host_mid": "12345", "offset": ""}
        result = signer.sign(params)

        assert "wts" in result
        assert "w_rid" in result
        assert result["host_mid"] == "12345"
        assert result["offset"] == ""

    def test_sign_filters_special_chars(self):
        """测试：过滤特殊字符"""
        signer = WBISigner()
        signer._mixin_key = "a" * 32
        signer._last_refresh = int(time.time()) + 1000

        params = {"msg": "test!'()*"}
        result = signer.sign(params)
        assert "!" not in result["msg"]
        assert "'" not in result["msg"]
        assert "(" not in result["msg"]
        assert ")" not in result["msg"]
        assert "*" not in result["msg"]

    def test_sign_sorts_params(self):
        """测试：参数按 key 排序"""
        signer = WBISigner()
        signer._mixin_key = "a" * 32
        signer._last_refresh = int(time.time()) + 1000

        params = {"z_param": "1", "a_param": "2", "m_param": "3"}
        result = signer.sign(params)

        keys = list(result.keys())
        # w_rid and wts are added, so check the original keys are sorted
        original_keys = [k for k in keys if k not in ("wts", "w_rid")]
        assert original_keys == sorted(original_keys)


class TestSignParams:
    """测试 sign_params 全局函数"""

    def test_sign_params_calls_signer(self):
        """测试：sign_params 调用签名器"""
        with patch('app.modules.wbi._signer') as mock_signer:
            mock_signer.sign.return_value = {"signed": True}
            result = sign_params({"test": "params"})
            assert result == {"signed": True}
            mock_signer.sign.assert_called_once_with({"test": "params"})
