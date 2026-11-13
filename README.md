# fc-certbot-src

[fc-certbot-ng](https://github.com/SmallKi-d/fc-certbot-ng) 的独立部署源码。基于 [devsapp/fc-certbot](https://github.com/devsapp/fc-certbot)，使用阿里云 DNS 验证域名、签发 Let's Encrypt 证书并上传 CAS，定时为 FC 自定义域名续签和更新证书。

## 运行环境

| 组件 | 版本 |
| --- | --- |
| 证书生成器 | Python 3.12、Certbot / ACME 5.10.0 |
| 域名管理器 | Node.js 20（FC 托管运行时） |
| CAS / AliDNS Python SDK | 3.9.5 / 4.6.1 |
| cryptography / PyOpenSSL | 50.0.2 / 26.4.0 |

使用 cryptography 处理 PKCS#8 / PKCS#1 RSA 私钥，支持多段域名后缀、子域名和通配符证书。构建与函数运行时相互独立，锁文件兼容应用中心的旧 npm。

## 部署与配置

应用中心通过 Git 仓库部署时，选择本仓库，部署清单为根目录 `s.yaml`。在**流水线／构建环境变量**中填写：

| 变量 | 用途 | 默认值 |
| --- | --- | --- |
| `FC_CERTBOT_ROLE_ARN` | RAM 角色完整 ARN，需要 DNS、CAS、FC 权限 | 必填 |
| `CERTBOT_EMAIL` | Let's Encrypt 账号邮箱 | 必填 |
| `FC_CERTBOT_ACCESS` | Serverless Devs 访问别名 | `default` |
| `CERT_GENERATOR_FUNCTION_NAME` | 证书生成函数名 | `cert-generator` |
| `FC_DOMAIN_MANAGER_FUNCTION_NAME` | 域名管理函数名 | `fc-domain-manager` |

角色 ARN 形如 `acs:ram::账号ID:role/角色名`。不要把这些部署变量只填到业务函数的运行时配置中；`s.yaml` 会将角色和邮箱写入对应函数配置。

本地部署：

```bash
git clone https://github.com/SmallKi-d/fc-certbot-src.git
cd fc-certbot-src
cp .env.example .env
# 编辑 .env，填写角色 ARN 和邮箱
PYTHON_BIN=python3.12 s deploy -y
```

构建需要 Linux、Python 3.12、Node.js 20 和 Serverless Devs v3。配置会在杭州与新加坡分别部署证书生成器和域名管理器，代码和依赖不需要手动上传。

部署完成后调用杭州的 `cert-generator`：

```json
{"domainName": "example.com.cn"}
```

签发通配符时使用 `*.example.com.cn`。域名必须由当前账号的 AliDNS 托管。证书上传 CAS 后绑定至 FC 自定义域名，保留自动生成的证书名前缀即可由每日任务管理轮换。

## 本地验证

```bash
cd cert-generator
PYTHON_BIN=python3.12 bash scripts/build-deps.sh
PYTHONPATH=python python3.12 -m unittest discover -s tests -v
cd ../fc-domain-manager
npm ci --omit=dev
npm test
```

完整配置见 [证书生成器说明](cert-generator/README.md) 和 [部署使用文档](readme.md)。真实签发需要账号凭证与可验证域名，默认 ACME 账号及证书文件写入 `/tmp/letsencrypt/`。
