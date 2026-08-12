# PDF to Word Local

一个注重隐私的离线 PDF 转 Word 工具，提供桌面界面、批量转换、可选公式识别和结构化质量报告。

> 当前为早期版本。0.2 版的公式 OCR 属于实验功能，主要识别 PDF 中以图片形式嵌入的公式。

## Windows 使用方法

1. 安装 Python 3.10 或更高版本。
2. 首次使用时双击 `install_windows.bat` 安装本地转换引擎。
3. 双击 `run_app.bat` 启动桌面程序。
4. 添加 PDF、选择输出目录，然后点击 Convert。

文件不会上传，默认使用本地开源 `pdf2docx` 引擎。

## 公式识别

公式 OCR 模型较大，因此不会随基础转换器默认安装。

1. 双击 `install_formula_ocr.bat` 安装一次。
2. 在桌面程序中勾选 **Recognize formula images (experimental)**。
3. 转换后对照原 PDF 检查 Word 文末的公式附录。

识别结果包含页码、原 PDF 边界框、LaTeX、置信度（模型提供时）、识别状态和 Word 渲染方式。Windows 安装了 Microsoft Office 和 `latex2mathml` 时，程序会通过 Office 自带的 `MML2OMML.XSL` 生成可编辑的 Word 原生公式；不可用时回退为可编辑 LaTeX 文本。

当前公式功能的边界：

- 识别尺寸适中的图片公式；
- 拒绝不含可靠数学特征的普通 OCR 文本；
- 跳过整页扫描图和过小图片；
- 暂不识别由 PDF 字体或矢量路径绘制的公式；
- 公式集中加入文末审阅区，暂不承诺可靠的原位置替换。

## 命令行

```powershell
pdf2word document.pdf --formula-ocr
pdf2word document.pdf --formula-ocr --max-formulae-per-page 12
```

每次转换生成 DOCX 和 `.conversion.json` 报告。报告记录转换引擎、页数、图片数量、公式识别结果、警告和耗时。

## 当前限制

- 暂不支持需要密码的 PDF；
- 暂不内置整页文字 OCR，纯扫描文档的正文可能不完整；
- 复杂表格、矢量公式和特殊字体无法保证完全还原；
- OCR 公式用于论文或生产环境前必须人工核对；
- PDF 是固定版式，Word 是流式版式，两者无法在所有情况下完全一致。

欢迎通过 issue 提交脱敏后的失败样例描述和复现步骤。请勿上传无权公开的文件。
