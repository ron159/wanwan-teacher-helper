# Windows 生产签名

标签发布必须通过 `scripts/sign_release.ps1`；缺少身份、证书过期、签名不可信或无时间戳会中止发布。唯一例外是用户明确授权的 `v0.2.0-preview.1` 未签名试用版，其 `signature.json` 明确记录 `UnsignedPreview`；其他版本标签仍强制检查生产签名。PR 构建保持未签名，仅供验证。

当前尚未配置实际生产身份。支持 Windows 当前账户证书库中的代码签名证书；证书私钥可以由已安装的硬件提供程序管理。CI 若使用允许导出的 PFX，配置 secrets `WANWAN_SIGNING_PFX_BASE64` / `WANWAN_SIGNING_PFX_PASSWORD`，以及 vars `WANWAN_SIGNING_THUMBPRINT` / `WANWAN_TIMESTAMP_URL`。证书材料不得写入仓库或聊天；秘密应由持有人在 GitHub 设置中配置。云签名服务需按已有服务接入，不能用自签名替代。

脚本使用 SHA256 文件摘要和 RFC 3161 时间戳，执行 `signtool verify /pa /all` 并检查签名者指纹。签名后才运行冻结程序验收、计算发行校验和。临时 PFX 和本次新导入的证书在 finally 清理；不导入信任根。

参考：[Microsoft SignTool](https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool)。本文件描述发布门槛，不代表当前已完成生产签名。
