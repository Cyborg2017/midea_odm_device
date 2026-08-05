"""美的云安全模块。

提供请求签名、密码加密、AES 加解密等安全能力。
"""
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from hashlib import md5, sha256
import hmac


class CloudSecurity:
    """云安全基类，提供签名和加解密能力。"""

    def __init__(self, login_key, iot_key, hmac_key, fixed_key=None, fixed_iv=None):
        self._login_key = login_key
        self._iot_key = iot_key
        self._hmac_key = hmac_key
        self._aes_key = None
        self._aes_iv = None
        self._fixed_key = format(fixed_key, 'x').encode("ascii") if fixed_key else None
        self._fixed_iv = format(fixed_iv, 'x').encode("ascii") if fixed_iv else None

    def sign(self, data: str, random: str) -> str:
        """生成 HMAC-SHA256 请求签名。"""
        msg = self._iot_key
        msg += data
        msg += random
        sign = hmac.new(self._hmac_key.encode("ascii"), msg.encode("ascii"), sha256)
        return sign.hexdigest()

    def encrypt_password(self, login_id, data):
        """加密用户密码（SHA256 + loginKey）。"""
        m = sha256()
        m.update(data.encode("ascii"))
        login_hash = login_id + m.hexdigest() + self._login_key
        m = sha256()
        m.update(login_hash.encode("ascii"))
        return m.hexdigest()

    def encrypt_iam_password(self, login_id, data) -> str:
        """加密 IAM 密码（子类实现）。"""
        raise NotImplementedError

    @staticmethod
    def get_deviceid(username):
        """根据用户名生成设备 ID（MD5 取前 16 位）。"""
        return md5(f"Hello, {username}!".encode("ascii")).digest().hex()[:16]

    def set_aes_keys(self, key, iv):
        """设置 AES 加解密密钥。"""
        if isinstance(key, str):
            key = key.encode("ascii")
        if isinstance(iv, str):
            iv = iv.encode("ascii")
        self._aes_key = key
        self._aes_iv = iv

    def aes_encrypt_with_fixed_key(self, data):
        """使用固定密钥进行 AES 加密。"""
        return self.aes_encrypt(data, self._fixed_key, self._fixed_iv)

    def aes_decrypt_with_fixed_key(self, data):
        """使用固定密钥进行 AES 解密。"""
        return self.aes_decrypt(data, self._fixed_key, self._fixed_iv)

    def aes_encrypt(self, data, key=None, iv=None):
        """AES 加密（ECB 或 CBC 模式）。"""
        if key is not None:
            aes_key = key
            aes_iv = iv
        else:
            aes_key = self._aes_key
            aes_iv = self._aes_iv
        if aes_key is None:
            raise ValueError("加密需要密钥")
        if isinstance(data, str):
            data = bytes.fromhex(data)
        if aes_iv is None:  # ECB 模式
            return AES.new(aes_key, AES.MODE_ECB).encrypt(pad(data, 16))
        else:  # CBC 模式
            return AES.new(aes_key, AES.MODE_CBC, iv=aes_iv).encrypt(pad(data, 16))

    def aes_decrypt(self, data, key=None, iv=None):
        """AES 解密（ECB 或 CBC 模式）。"""
        if key is not None:
            aes_key = key
            aes_iv = iv
        else:
            aes_key = self._aes_key
            aes_iv = self._aes_iv
        if aes_key is None:
            raise ValueError("解密需要密钥")
        if isinstance(data, str):
            data = bytes.fromhex(data)
        if aes_iv is None:  # ECB 模式
            return unpad(AES.new(aes_key, AES.MODE_ECB).decrypt(data), len(aes_key)).decode()
        else:  # CBC 模式
            return unpad(AES.new(aes_key, AES.MODE_CBC, iv=aes_iv).decrypt(data), len(aes_key)).decode()


class MeijuCloudSecurity(CloudSecurity):
    """美的美居云安全实现。"""

    def __init__(self, login_key, iot_key, hmac_key):
        super().__init__(login_key, iot_key, hmac_key,
                         10864842703515613082)

    def encrypt_iam_password(self, login_id, data) -> str:
        """加密 IAM 密码（双重 MD5）。"""
        md = md5()
        md.update(data.encode("ascii"))
        md_second = md5()
        md_second.update(md.hexdigest().encode("ascii"))
        return md_second.hexdigest()
