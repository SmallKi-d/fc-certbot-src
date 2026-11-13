# 阿里云 DNS 证书自动签发与上传

运行环境：Linux、Python 3.12。入口保持为 `index.handler`，通过 Certbot 的 DNS-01 验证签发 RSA 证书，再上传到阿里云 CAS。

依赖版本：

- `certbot==5.10.0`、`acme==5.10.0`
- `alibabacloud_cas20200407==3.9.5`
- `alibabacloud_alidns20150109==4.6.1`
- `cryptography==50.0.2`、`pyOpenSSL==26.4.0`

私钥通过 `cryptography` 读取和转换，支持 Certbot 输出的 PKCS#8 和 PKCS#1 RSA PEM，不再依赖系统 `openssl rsa` 的默认输出格式或已移除的 PyOpenSSL 接口。

## 安装与部署

在与部署环境相同的 Linux 架构和 Python 3.12 环境下执行：

```bash
PYTHON_BIN=python3.12 bash scripts/build-deps.sh
```

脚本先安装到临时目录，成功后替换 `python/`，旧依赖会备份到系统临时目录。不要将 Python 3.10 的旧二进制依赖与新依赖混合使用。`cryptography 50.0.2` 的 x86_64 Linux wheel 要求 glibc 2.34 或更新版本；其他架构应在目标环境重新安装。

默认从阿里云 PyPI 镜像安装，可通过 `PIP_INDEX_URL` 指定其他源。

将项目和 `python/` 一并部署，函数运行时选择 Python 3.12，并确保 `python/` 在 `PYTHONPATH` 中（例如函数计算代码目录为 `/code` 时设置为 `/code/python`）。本地验证：

```bash
PYTHONPATH=python python3.12 -m unittest discover -s tests -v
PYTHONPATH=python python3.12 -c 'from certbot.main import main; main(["--version"])'
```

## 配置

必需环境变量：

- `CERTBOT_EMAIL`：用于 ACME 账号注册的真实邮箱。

函数计算中使用部署配置指定的 RAM 角色，入口会在每次调用时从 `context.credentials` 更新临时凭证，供 SDK 与 Certbot 子进程使用。不要手动固定角色临时密钥。

本地调用时设置 `ALIBABA_CLOUD_ACCESS_KEY_ID`、`ALIBABA_CLOUD_ACCESS_KEY_SECRET`；使用 STS 临时凭证时另设 `ALIBABA_CLOUD_SECURITY_TOKEN`。凭证需要 DNS 记录查询、添加、修改、删除及 CAS 证书查询、上传、删除权限。

可选环境变量：

| 变量 | 默认值 / 用途 |
| --- | --- |
| `FC_REGION` | 新加坡使用对应 AliDNS 端点，其他地区默认杭州端点 |
| `CERTBOT_CONFIG_DIR` | `/tmp/letsencrypt/config` |
| `CERTBOT_WORK_DIR` | `/tmp/letsencrypt/work` |
| `CERTBOT_LOGS_DIR` | `/tmp/letsencrypt/logs` |
| `CERTBOT_DNS_PROPAGATION_SECONDS` | `30`，写入 TXT 后等待的秒数 |
| `CERTBOT_SERVER` | Let's Encrypt 正式环境 ACME 地址 |

测试签发可将 `CERTBOT_SERVER` 设为 `https://acme-staging-v02.api.letsencrypt.org/directory`。测试环境签发的证书不被浏览器信任。

调用事件示例（也支持 JSON 字符串或字节）：

```json
{"domainName": "example.com", "certName": "my-certificate"}
```

`certName` 可省略；传入已有名称时，证书将在到期前七天内重新签发并替换。域名必须已由当前账号的阿里云 DNS 管理，支持根域名、子域名和单个通配符域名。当前域名拆分逻辑适用于 `example.com` 这样的两段主域名，`example.co.uk` 等多段后缀需要另外适配。

Certbot hook 使用当前 Python 解释器及项目实际路径，不再要求代码固定在 `/code`。证书默认存放在函数计算可写的 `/tmp`；需要跨实例保留 ACME 账号及续期状态时，将上述目录配置到持久化存储。

## 验证范围

自动化测试使用真实 SDK 请求/响应模型及真实 RSA 密钥，模拟 DNS/CAS 网络请求和 ACME 签发结果。真实签发和上传需要部署账号凭证与可验证域名。
